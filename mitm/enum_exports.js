// enum_exports.js — list libclient.so exports matching loader/parser keywords (no hooks, safe)
var names = [];
Module.enumerateExports('libclient.so').forEach(function(e) {
    var n = e.name.toLowerCase();
    if (n.indexOf('get_file') >= 0 || n.indexOf('decrypt') >= 0 ||
        n.indexOf('marshal') >= 0 || n.indexOf('patch') >= 0 ||
        n.indexOf('package') >= 0 || n.indexOf('npk') >= 0) {
        send(e.type + ' ' + e.name + ' @ ' + e.address);
    }
});
send('ENUM-DONE');
