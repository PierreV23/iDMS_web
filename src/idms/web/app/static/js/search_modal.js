function SearchModal(data) {
    this.callback_function = data['callback_function']
    this.current_attrs = null
    this.api_available_attrs = data['api_available_attrs']
    this.api_attrvalues_for_search = data['api_attrvalues_for_search']
    this.api_searchtable = data['api_searchtable']
    this.select_function = data['select_function']
    this.context = data['context']
    if ('format' in data) {
      this.format = data['format']
    } else {
      this.format = 'plain'
    }
    this.requestid = 0
    search_modal = this

    this.filltable = function(update_attrs) {
        $('#searchtable').addClass('pending')
        $('#progress-bar').addClass('show-progress')
        search_data = this.form_data()
        id = Date.now()
        search_data['id'] = id
        search_data['format'] = this.format
        search_modal = this
        $.ajax({
            type: 'POST',
            url: search_modal.api_searchtable,
            data: JSON.stringify(search_data),
            contentType: 'application/json;charset=UTF-8',
            success: function (data) {
                if (data['id'] == id) {
                    $('#searchtable').bootstrapTable('destroy').bootstrapTable(data).removeClass('pending')
                    $('#progress-bar').removeClass('show-progress')
                    search_modal.current_attrs = data['attrs']
                    if (update_attrs) {
                        search_modal.load_attrs()
                    }
                }
            }
        })
    }

    this.add_metadata_search = function() {
        attr = $('#meta-attr-select').find(":selected").text();
        value = $('#meta-value-select').find(":selected").text();
        $('#meta-cards').append(`
            <div class="card meta-card">
              <div class="card-body">
                <h5 class="card-title meta-attr">
                  ${attr}
                </h5>
                <button type="button" class="close meta-remove"><h5>x</h5></button>
                <p class="card-text">${value}</p>
              </div>
            </div>`)
    }

    this.select_wrapper = function(target, value, event) {
      search_modal.select_function(search_modal, target, value, event)
    }

    this.close = function() {
      $('#searchModal').modal('hide').modal('dispose').remove()
    }

    this.show = function() {
        insert_search_modal()
        $('[data-toggle="tooltip"]').tooltip()
        $('#searchModal').modal('show')
        $(document).off('click.search').off("select.search").off("click-row.bs.table.search")
        $('select').selectpicker();
        search_modal=this

        if (this.select_function) {
          $(document).on('click-row.bs.table.search', '#searchtable', this.select_wrapper)
        }

        $(document).on('changed.bs.select', '#meta-attr-select', function (e, clickedIndex, isSelected, previousValue) {
            // Set the selected attr on the button
            attr_name = $('#meta-attr-select').selectpicker('val')
            $('.meta-value-option').remove()
            search_data = search_modal.form_data()
            search_data['attr'] = attr_name
            $('#progress-bar').addClass('show-progress')
            $.ajax({
                type: 'POST',
                url: search_modal.api_attrvalues_for_search,
                data: JSON.stringify(search_data),
                contentType: 'application/json;charset=UTF-8',
                success: function (data) {
                      $('#meta-value-select')
                          .find('.meta-value-option')
                          .remove();

                      data.forEach(function (option) {
                          $('#meta-value-select').append(
                              `<option class="meta-value-option">${option}</option>`
                          );
                      });

                      $('#meta-value-select')
                          .val("default_value")
                          .attr('disabled', false)
                          .selectpicker('refresh')
                          .focus();

                      $('#progress-bar').removeClass('show-progress');
                }
            })
        })

        $(document).on('changed.bs.select', '#meta-value-select', function () {
            search_modal.filltable()
            $('#add_meta').attr('disabled', false)
        })

        $(document).on('click.search', '#add_meta', function () {
            search_modal.add_metadata_search()
            search_modal.init_metadata_search()
            $('#meta-attr-select').focus()
        })

        $(document).on('click.search', '.meta-remove', function() {
            $(this).parentsUntil('.meta-card').parent().remove()
            search_modal.filltable(true)
            //search_modal.load_attrs()
        })

        $('#searchReset').on('click', function() {
            search_modal.init_searchform()
        })

        $('#searchtext').on('input', function (data) {
            val = $(this).val()
            id = Date.now()
            if (search_modal.requestid != 0) {
                clearTimeout(search_modal.requestid)
            }
            search_modal.requestid = setTimeout(function () {
                search_modal.filltable(true)
            }, 1000)
        })

        this.init_searchform()
    }

    this.form_data = function() {
        keywords = $('#searchtext').val().split(" ").filter(word => word !== '');
        attr = $('#meta-attr-select').find(":selected").text();
        value = $('#meta-value-select').find(":selected").text();
        metadata = {}
        if ((attr != 'Select attr ...') && (value != 'Select value ...') && (attr != "") && (value != "")) {
            metadata[attr] = value
        }
        $('.meta-attr').each(function (i, obj) {
            attr = $(this).html().trim()
            value = $(this).siblings('p').html().trim()
            metadata[attr] = value
        })
        return {
            'keywords': keywords,
            'meta': metadata
        }
    }

    this.init_metadata_search = function() {
        $('.meta-attr-option').remove()
        $('.meta-value-option').remove()
        $('#meta-attr-select').val("default_attr")
        $('#meta-value-select').val("default_value")
        $('#add_meta').attr('disabled', true)
        this.load_attrs()
    }

    this.init_searchform = function() {
        this.current_attrs = null
        $('#searchtable').bootstrapTable('destroy')
        $('#searchtext').val('')
        $('#meta-cards').html('')
        this.init_metadata_search()
    }

    this.load_attrs = function() {
        // Function to load valid attribute names in the attribute selection button
        // on the right
        $('#meta-attr-select').attr('disabled', true)
        $('#meta-value-select').attr('disabled', true)
        $('.meta-attr-option').remove()
        $('#meta-value-select').val('default_value').selectpicker('refresh')
        $('#progress-bar').addClass('show-progress')
        if (this.current_attrs !== null) {
            this.current_attrs.forEach(function (value) {
                $('#meta-attr-select').append(
                    `<option class="meta-attr-option">${value}</option>`
                )
            })
            $('#progress-bar').removeClass('show-progress')
            $('#meta-attr-select')
                .attr('disabled', false)
                .val("default_attr")
                .selectpicker('refresh');
        } else {
            formdata = this.form_data()
            id = Date.now()
            formdata['id'] = id
            $.ajax({
                type: 'POST',
                url: this.api_available_attrs,
                data: JSON.stringify(formdata),
                contentType: 'application/json;charset=UTF-8',
                success: function (data) {
                    data.forEach(function (value) {
                        $('#meta-attr-select').append(
                            `<option class="meta-attr-option">${value}</option>`
                        )
                    })
                    $('#progress-bar').removeClass('show-progress')
                    $('#meta-attr-select')
                        .attr('disabled', false)
                        .val("default_attr")
                        .selectpicker('refresh')
                        .focus();
                }
            })
        }
    }
}


function insert_search_modal() {
    $('#searchModal').remove()
    $('body').append(`
<div class="modal" id="searchModal">
  <div class="modal-dialog modal-xl" role="document">
    <div class="modal-content">
      <div class="modal-header">
        <h4 class="modal-title" id="exampleModalLabel">iRODS Dataset search</h4>
        <button type="button" class="close" data-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">&times;</span>
        </button>
      </div>
      <div class="modal-body" id="searchBody">
        <div class="container">
          <div class="row">
            <div class="col-md-3">
              <h4>Metadata</h4>
            </div>
            <div class="col-md-9">
              <h4>Collection path keywords</h4>
            </div>
          </div>
          <div class="row">
            <div class="col-md-3">
              <div class="float-left">
                <select class="attrselect" id="meta-attr-select" disabled data-live-search="true" tabindex="0">
                    <option id="meta-attr-default" value="default_attr" selected disabled>Select attr ...</option>
                </select>
                <select class="valueselect" data-live-search="true" id="meta-value-select" disabled tabindex="1">
                    <option id="meta-value-default" value="default_value" selected disabled>Select value ...</option>
                </select>
              </div>
            </div>

            <div class="col-md-9">
              <div>
                <input class="form-control" id="searchtext" placeholder="Enter your search text" tabindex="3">
              </div>
              <div class="divider" id="progress-bar"></div>
            </div>
          </div>
          <div class="row">
            <div class="col-md-3">
              <center><button class="btn btn-outline" id="add_meta" disabled tabindex="2" data-toggle="tooltip" title="Add meta to search parameters"><span class="fa-solid fa-arrow-down"></span></button></center>
            </div>
          </div>
          <div class="row">
            <div class="col-md-3" id="meta-cards">

            </div>
            <div class="col-md-9">
              <div>
                <table class="table" id="searchtable">
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
        <button type="button" class="btn btn-primary" id="searchReset">Reset</button>
      </div>
    </div>
  </div>
</div>`)
}