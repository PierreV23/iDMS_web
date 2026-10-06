#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Nov 18 15:16:25 2019

@author: wierinve
"""
import os
import csv
import ctypes
import json
import markdown
from flask import Blueprint, Response, render_template, request, url_for, send_file, jsonify, abort
from flask_login import current_user, login_required
import urllib.parse
from irods.exception import CAT_NO_ACCESS_PERMISSION, SYS_FILE_DESC_OUT_OF_RANGE
from idms.common.irods.irods_sessions import irods_manager
from idms.common.filesys.fs_irods import fs_irods

from typing import Callable, Optional

bp = Blueprint('docviewer', __name__, url_prefix='/docviewer')

csv.field_size_limit(int(ctypes.c_ulong(-1).value // 2))

class DocViewerManager:
    def  __init__(self):
        self._object_handlers = {}
        self._extension_map = {}
        
    def document_handler(self, objecttype):
        def decorator(f):
            self.register_handler(objecttype, f)
            return f
        return decorator
    
    def register_handler(self, objecttype, handler):
        self._object_handlers[objecttype] = handler
    
    def register_mapping(self, objecttype, *extensions):
        for ext in extensions:
            normalized = ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
            self._extension_map[normalized] = objecttype
            
    def load_mappings(self, filename):
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                self._extension_map = json.load(f)
            
    def resolve_handler(self, filename: str) -> Optional[Callable]:
            """Find the appropriate handler for a given filename."""

            # Find file type
            matching_filetypes = [ filetype for extension, filetype in self._extension_map.items() if filename.endswith(extension) ]
            if len(matching_filetypes) != 1:
                return None
                
            # Find handler
            return self._object_handlers.get(matching_filetypes[0])                   
                    
    def render(self, obj, path, current_user = None):
        """Route file rendering to registered handler or default download stream."""
        handler = self.resolve_handler(path)
        
        if handler:
            return handler(obj=obj, path=path, current_user=current_user)
        
        # Default Fallback: Stream raw file content
        objectfile = obj.open('r')
        return send_file(
            objectfile,
            download_name=os.path.basename(path),
            as_attachment=False,
            mimetype="application/octet-stream"
        )      


doc_viewer_manager = DocViewerManager()

@bp.route('/serve_object')
@login_required
def serve_object():
    
    path = urllib.parse.unquote(request.args.get('path', '/', type=str))
    
    with irods_manager.session(current_user) as session:
        try:
            obj = fs_irods(session=session).getfile(path)
        except Exception:
            abort(404, description="Dataobject not found")
            
        return doc_viewer_manager.render(obj=obj, path=path, current_user=current_user)    
    

@doc_viewer_manager.document_handler('textfile')
def render_text(obj, path, **kwargs):
    objectfile = obj.open('r')
    return send_file(
        objectfile,
        download_name=os.path.basename(path),
        as_attachment=False,
        mimetype="text/plain"
    )


@doc_viewer_manager.document_handler('csv')
def render_csv(obj, path, **kwargs):
    with obj.open('r') as fobj:
        csvtext = fobj.read().decode('utf-8')
        try:
            dialect = csv.Sniffer().sniff(csvtext[:1024], delimiters=',;\t')
        except Exception:
            dialect = None
        objcsv = csv.reader(csvtext.split('\n'), dialect=dialect)
        return render_template('csvview.html', data=objcsv)


@doc_viewer_manager.document_handler('pdf')
def render_pdf(obj, path, **kwargs):
    objectfile = obj.open('r')
    response = send_file(
        objectfile,
        download_name=os.path.basename(path),
        as_attachment=False,
        mimetype="application/pdf"
    )
    # Explicitly set content disposition to inline
    response.headers['Content-Disposition'] = f'inline; filename="{os.path.basename(path)}"'
    return response    

@doc_viewer_manager.document_handler('markdown')
def render_markdown(obj, path, **kwargs):
    with obj.open('r') as fobj:
        return markdown.markdown(fobj.read().decode('utf-8'), extensions=['fenced_code', 'tables', 'toc'])
    

@doc_viewer_manager.document_handler('image')
def render_image(obj, path, **kwargs):
    image_url = url_for('docviewer.serve_image', path=path)
    return f'<img height="100%" src="{image_url}">'


@doc_viewer_manager.document_handler('html')
def render_html(obj, path, sanitize=True, **kwargs):
    """Render HTML files safely within the document viewer iframe."""
    with obj.open('r') as fobj:
        raw_content = fobj.read()
        
        # Decode bytes if needed
        if isinstance(raw_content, bytes):
            content = raw_content.decode('utf-8', errors='replace')
        else:
            content = raw_content

    return content, 200, {'Content-Type': 'text/html; charset=utf-8'}


# HELPER FUNCTIONS
@bp.route('/serve_image')
def serve_image():
    path = urllib.parse.unquote(request.args.get('path', '/', type=str))
    with irods_manager.session(current_user) as session:
        obj = fs_irods(session=session).getfile(path)
        imagefile = obj.open('r')
    return send_file(imagefile, download_name=os.path.split(path)[1],
                     as_attachment=False)


@bp.route('_access')
def test_access():
    path = urllib.parse.unquote(request.args.get('path', '/', type=str))
    with irods_manager.session(current_user) as session:
        obj = fs_irods(session=session).getfile(path)
        try:
            objectfile = obj.open('r')
            access = 'GRANTED'
            objectfile.close()
        except (CAT_NO_ACCESS_PERMISSION, SYS_FILE_DESC_OUT_OF_RANGE):
            access = 'DENIED'
    return jsonify({
        'access': access
    })


@bp.route('/download_object')
def download_object():
    path = urllib.parse.unquote(request.args.get('path', '/', type=str))
    with irods_manager.session(current_user) as session:
        objectfile = fs_irods(session=session).getfile(path).open('r')
        AA = send_file(objectfile, download_name=os.path.split(path)[1],
                         as_attachment=True)
    return AA


@bp.route('/serve_file')
def serve_file():
    """ Serve any iRODS dataobject
        
        args:
            path: path to irods file

        This function honors the Range request header to serve partial irods dataobjects
    """
    path = urllib.parse.unquote(request.args.get('path', '/', type=str))
    range_header = request.headers.get('Range')
    with irods_manager.session(current_user) as session:
        try:
            obj = fs_irods(session=session).getfile(path)
        except:
            abort(404, description="Dataobject not found")

        file_size = obj.filesize()
        if not range_header:
        # If no Range header, send the entire file
            objectfile = obj.open('r')        
            return send_file(objectfile, mimetype="application/octet-stream")
        try:
            # Parse the Range header (e.g., "bytes=0-1024")
            bytes_range = range_header.strip().split('=')[1].split('-')
            if (bytes_range[0]):
                start = int(bytes_range[0])
                end = int(bytes_range[1]) if bytes_range[1] else file_size - 1
            else:
                start = file_size - int(bytes_range[1])
                end = file_size - 1
        except (IndexError, ValueError):
            # Handle invalid Range header format
            abort(416, description="Invalid Range header")

        # Ensure the requested range is valid
        if start >= file_size or end >= file_size or start > end:
            abort(416, description="Requested range is not satisfiable")

        chunk_length = end - start + 1

        objectfile = obj.open('r')

        def generate(length):
            objectfile.seek(start)
            while length > 0:
                # Read 1MB chunks
                chunk = objectfile.read(min(1048576, length))
                if not chunk:
                    break
                yield chunk
                length -= len(chunk)

        # Create the response
        response = Response(generate(chunk_length), 206) #, mimetype='video/mp4')
        response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Content-Length'] = str(chunk_length)

        return response


# @bp.route('/serve_object')
# def serve_object():
#     path = urllib.parse.unquote(request.args.get('path', '/', type=str))
#     filename, file_extension = os.path.splitext(path.lower())
#     coll, dataobject = os.path.split(path)
#     with irods_manager.session(current_user) as session:

#         # Handle IGV extensions        
#         if file_extension in [".bam", ".cram"]:
#             format=file_extension.strip(".")

#             # Get user settings for reference genome
#             hosted_genome = None
#             ref_object = None
#             reftype = current_user.settings.get('igv::reftype', None)
#             if reftype == 'hosted':
#                 hosted_genome = current_user.settings.get('igv::genome', 'hg38')
#             elif reftype == 'object':
#                 ref_object = current_user.settings.get('igv::fasta')
            
#             return render_template('igv.html', coll=coll, path=path, name=dataobject, format=format,
#                 reftype=reftype, ref_object=ref_object, genome=hosted_genome)  

#         obj = fs_irods(session=session).getfile(path)
#         objectfile = obj.open('r')
#         mimetype = None
#         # Handle csv files
#         if file_extension in [".csv", ".tsv"]:
#             output = csvconvert(objectfile)
#             return output
#         # Handle markdown files
#         if file_extension in [".md"]:
#             output = mdconvert(objectfile)
#             return output
#         # Handle image files
#         if file_extension in [".jpg", ".png"]:
#             output = '<img height="100%" src="' + url_for('docviewer.serve_image') +  "?path=" + path + '">'
#             return output
#         # Handle text files
#         if file_extension in [".re", ".cfg", ".xml", ".out", ".yml", ".yaml", ".err", ".log", ".metrics", ".vcf" ]:
#             mimetype = "text/plain"

#         returnobject = send_file(objectfile, download_name=os.path.split(path)[1],
#                                     as_attachment=False, mimetype=mimetype, max_age=-1)
#     return returnobject


