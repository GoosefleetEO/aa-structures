$(document).ready(function () {

    /* retrieve generated data from HTML page */
    var elem = document.getElementById('dataExport');
    var listDataUrl = elem.getAttribute('data-listDataUrl');
    var titleAlliance = elem.getAttribute('data-titleAlliance');
    var titleCorporation = elem.getAttribute('data-titleCorporation');
    var titleRegion = elem.getAttribute('data-titleRegion');
    var titleSolarSystem = elem.getAttribute('data-titleSolarSystem');
    var titleCategory = elem.getAttribute('data-titleCategory');
    var titleGroup = elem.getAttribute('data-titleGroup');
    var Reinforced = elem.getAttribute('data-Reinforced');
    var State = elem.getAttribute('data-State');
    var PowerMode = elem.getAttribute('data-PowerMode');
    var dataTablesPageLength = elem.getAttribute('data-dataTablesPageLength');
    var dataTablesPaging = (elem.getAttribute('data-dataTablesPaging') == 'True');

    /* dataTable def */
    $('#tab_structures').DataTable({
        ajax: {
            url: listDataUrl,
            dataSrc: '',
            cache: false
        },

        columns: [
            { data: 'corporation_icon' },
            { data: 'owner' },
            { data: 'location' },
            { data: 'type_icon' },
            { data: 'type' },
            { data: 'structure_name' },
            { data: 'services' },
            {
                data: 'fuel_expires_at',
                render: {
                    _: 'display',
                    sort: 'timestamp'
                }
            },
            {
                data: 'last_online_at',
                render: {
                    _: 'display',
                    sort: 'timestamp'
                }
            },
            { data: 'reinforcement' },
            { data: 'state_details' },

            { data: 'alliance_name' },
            { data: 'corporation_name' },
            { data: 'region_name' },
            { data: 'solar_system_name' },
            { data: 'category_name' },
            { data: 'group_name' },
            { data: 'is_reinforced_str' },
            { data: 'state_str' },
            { data: 'power_mode_str' }
        ],

        lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],

        paging: dataTablesPaging,

        pageLength: dataTablesPageLength,

        columnDefs: [
            { "sortable": false, "targets": [0, 3, 4, 6] },
            { "visible": false, "targets": [11, 12, 13, 14, 15, 16, 17, 18, 19] }
        ],

        order: [[1, "asc"], [5, "asc"]],

        filterDropDown:
        {
            columns: [
                {
                    idx: 11,
                    title: titleAlliance
                },
                {
                    idx: 12,
                    title: titleCorporation
                },
                {
                    idx: 13,
                    title: titleRegion
                },
                {
                    idx: 14,
                    title: titleSolarSystem
                },
                {
                    idx: 15,
                    title: titleCategory
                },
                {
                    idx: 16,
                    title: titleGroup
                },
                {
                    idx: 17,
                    title: Reinforced
                },
                {
                    idx: 18,
                    title: State
                },
                {
                    idx: 19,
                    title: PowerMode
                }
            ],
            bootstrap: true
        },

        createdRow: function (row, data, dataIndex) {
            if (data['is_reinforced']) {
                $(row).addClass('danger');
            }
        }

    });
});