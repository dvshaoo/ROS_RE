var mods = Process.enumerateModules();
var found = [];
mods.forEach(function(m){
  if (m.name.toLowerCase().indexOf('client') !== -1) {
    found.push(m.name + ' @ ' + m.base + ' size=0x' + m.size.toString(16) + ' path=' + m.path);
  }
});
send(found.join('\n'));
send('TOTAL_MODULES=' + mods.length);
