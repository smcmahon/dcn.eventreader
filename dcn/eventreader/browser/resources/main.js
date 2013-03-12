jQuery(function ($) {
    // event view overlays
    $('table.ploneCalendar li.caleventtitle a').prepOverlay({
        subtype:'ajax',
        formselector: '#form',
        closeselector: '#form-buttons-cancel',
        afterpost: function (el, data_parent) {
            if (el.find('dl.portalMessage:visible')) {
                data_parent.overlay().close();
                location.replace(location.href);
                }
            }
        });

});
