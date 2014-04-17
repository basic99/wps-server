function validateEmail(email) {
    "use strict";
    // var reg = /^\w+([-+.']\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*$/;
    var reg = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}\b/i;
    if (reg.test(email)) {
        return true;
    } else {
        return false;
    }
}

$(document).ready(function() {
    "use strict";
    $('#submit_btn').click(function(evt) {
        $('.form-group').removeClass('has-error');
        evt.preventDefault();
        var firstname = $('#FirstName').val();
        var lastname = $('#LastName').val();
        var affil = $('#Affil').val();
        var username = $('#UserName').val();
        var passwd = $('#Password').val();
        var email = $('#Email').val();

        if (firstname.length === 0) {
            $('.FirstName').addClass('has-error');
        } else if (lastname.length === 0) {
            $('.LastName').addClass('has-error');
        } else if (!validateEmail(email)) {
            $('.Email').addClass('has-error');
        } else if (affil.length === 0) {
            $('.Affil').addClass('has-error');
        } else if (username.length === 0) {
            $('.UserName').addClass('has-error');
        } else if (passwd.length < 6) {
            $('.Password').addClass('has-error');
        } else {
            document.forms.fm1.submit();
        }
    });

});