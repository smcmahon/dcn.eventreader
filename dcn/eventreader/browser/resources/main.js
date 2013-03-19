jQuery(function ($) {
    // event view overlays
    $('table.ploneCalendar li.caleventtitle a, dd.infobuttons a').prepOverlay({
        subtype:'ajax',
        formselector: '#form',
        closeselector: '#form-buttons-cancel',
        filter: common_content_filter,
        noform: function(el) {return $.plonepopups.noformerrorshow(el, 'redirect');},
        redirect: '@@caledit',
        afterpost: function (el, data_parent) {
            var val = el.find('#form-widgets-recurs').val();
            // console.log(val);
            if (val === "Irregularly") {
                el.find("#formfield-form-widgets-end").hide();
                el.find("#formfield-form-widgets-start").hide();
            } else {
                el.find("#formfield-form-widgets-dates").hide();
            }
        }
    });

    function show_hide_dates() {
        var val = $('#form-widgets-recurs').val();

        if (val === "Irregularly") {
            $("#formfield-form-widgets-end").hide();
            $("#formfield-form-widgets-start").hide();
            $("#formfield-form-widgets-dates").slideDown();
        } else {
            $("#formfield-form-widgets-dates").hide();
            $("#formfield-form-widgets-start").slideDown();
            $("#formfield-form-widgets-end").slideDown();
        }
    }

    $(document).delegate('#form-widgets-recurs', 'change', function (event) {
        // console.log($('#form-widgets-recurs').val());
        show_hide_dates();
    });

    $(document).on('loadInsideOverlay', function () {
        // console.log('loadInsideOverlay');
        show_hide_dates();
    });

});


