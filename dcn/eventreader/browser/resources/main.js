jQuery(function ($) {
    // event view overlays
    $('table.ploneCalendar li.caleventtitle a, dd.infobuttons a').prepOverlay({
        subtype:'ajax',
        formselector: '#form',
        closeselector: '#form-buttons-cancel',
        // filter: common_content_filter,
        noform: function(el) {return $.plonepopups.noformerrorshow(el, 'redirect');},
        redirect: '@@caledit'
        // afterpost: function (el, data_parent) {
        //     if (el.find('dl.portalMessage:visible')) {
        //         data_parent.overlay().close();
        //         location.replace(location.href);
        //         }
        //     }
        });

});


