$(document).ready(function(){
    
    /* retrieve generated data from HTML page */
    var elem = document.getElementById('dataExport');
    var listDataUrl = elem.getAttribute('data-listDataUrl');    
    var titleAlliance = elem.getAttribute('data-titleAlliance');
    var titleCorporation = elem.getAttribute('data-titleCorporation');
    var titleRegion = elem.getAttribute('data-titleRegion');
    var titleSolarSystem = elem.getAttribute('data-titleSolarSystem');
    var titleCategory = elem.getAttribute('data-titleCategory');
    var titleGroup = elem.getAttribute('data-titleGroup');
    var titleType = elem.getAttribute('data-titleType');
    var Reinforced = elem.getAttribute('data-Reinforced');
    var State = elem.getAttribute('data-State');
    var LowPower = elem.getAttribute('data-LowPower');

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
            { data: 'reinforcement' },
            { data: 'fuel_expires',
                render: {
                    _: 'display',
                    sort: 'timestamp'
                }
            },
            { data: 'state_details' },

            { data: 'alliance_name' },
            { data: 'corporation_name' },
            { data: 'region_name' },
            { data: 'solar_system_name' },
            { data: 'category_name' },
            { data: 'group_name' },
            { data: 'type_name' },
            { data: 'is_reinforced_str' },
            { data: 'state_str' },
            { data: 'is_low_power_str' }
        ],
                    
        lengthMenu: [[7, 15, 25, 50, -1], [7, 15, 25, 50, "All"]],
        
        columnDefs: [
            { "sortable": false, "targets": [0, 3, 4, 6] },
            { "visible": false, "targets": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19] }
        ],
        
        order: [ [ 1, "asc" ], [ 5, "asc" ] ],
        
        filterDropDown:
        {
            columns: [                                       
                {
                    idx: 10,
                    title: titleAlliance
                },
                {
                    idx: 11,
                    title: titleCorporation
                },
                {
                    idx: 12,
                    title: titleRegion
                },
                {
                    idx: 13,
                    title: titleSolarSystem
                },
                {
                    idx: 14,
                    title: titleCategory
                },
                {
                    idx: 15,
                    title: titleGroup
                },  
                {
                    idx: 16,
                    title: titleType
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
                    title: LowPower
                }
            ],
            bootstrap: true
        },

        createdRow: function( row, data, dataIndex ) 
        {
            if (data['is_reinforced'])
            {
                $(row).addClass('danger');
            }               
        }
        
    });       
});