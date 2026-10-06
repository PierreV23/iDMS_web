import os
import urllib.parse

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user
from idms.common.filesys.fs_irods import fs_irods
from idms.common.irods.irods_sessions import irods_manager

from idms.web.app.plugin import BasePlugin

PLUGIN_NAME = 'igv'

# index file extensions used in the igv viewer.
INDEX_FORMATS = { 'fasta': 'fai',
                'bam': 'bai',
                'cram': 'crai'}

class IGVPugin(BasePlugin):
    name = PLUGIN_NAME
    description = 'Interactive Genome Viewer'
    optional = True
    def setup(self):
        self.register_viewer_mapping('bam', '.bam', '.cram')
        self.register_viewer_handler('bam', self.render_igv)
        bp = Blueprint(
            PLUGIN_NAME,
            __name__,
            template_folder='templates',
            static_folder='static',
            url_prefix=f'/{PLUGIN_NAME}'
        )
        @bp.route("/check_index")
        def check_index():
            result = find_index()
            return jsonify(result)
        self.app.register_blueprint(bp)

    @staticmethod
    def render_igv(obj, path, current_user=None, **kwargs):
        coll, dataobject = os.path.split(path)
        _, ext = os.path.splitext(path)
        fmt = ext.strip(".")
        
        reftype = current_user.settings.get('igv::reftype', None) if current_user else None
        hosted_genome = current_user.settings.get('igv::genome', 'hg38') if reftype == 'hosted' else None
        ref_object = current_user.settings.get('igv::fasta') if reftype == 'object' else None
        
        return render_template(
            'igv.html', coll=coll, path=path, name=dataobject,
            format=fmt, reftype=reftype, ref_object=ref_object, genome=hosted_genome
        )

def find_index():
    '''
    finds an index file for a file, by checking the existence of:
    filename.extension.index_extension or filename.index_extension
    in the location of the original file
    '''
    path = urllib.parse.unquote(request.args.get('path', '/', type=str))
    filename, file_extension = os.path.splitext(path.lower())
    format = file_extension.strip(".")
    
    with irods_manager.session(current_user) as session:

        # Handle IGV extensions        
        if format in INDEX_FORMATS:           
            index_format = INDEX_FORMATS[format]
            # Search for index files, both with and without the original extension
            index_path = None
            for index_path in [f'{path}.{index_format}', f'{os.path.splitext(path)[0]}.{index_format}']:
                if fs_irods(session=session).fileexists(index_path):
                    break
            return {"exists": True, "index_path": index_path}

    return {"exists": False, "index_path": None}

