// Frida Gadget script — hooks getaddrinfo() to redirect easebar.com domains
// to our local MITM server at 192.168.100.8

var TARGET_IP = "192.168.100.8";

var DOMAINS_TO_REDIRECT = [
    "g61.gph.easebar.com",
    "gph.easebar.com",
    "g61.update.easebar.com",
    "gdl.easebar.com",
    "g61.patch.easebar.com",
    "drpf-h45na.proxima.nie.netease.com",
    "static.easebar.com",
    "api.easebar.com",
    "auth.easebar.com"
];

function shouldRedirect(hostname) {
    if (hostname === null) return false;
    for (var i = 0; i < DOMAINS_TO_REDIRECT.length; i++) {
        if (hostname.indexOf(DOMAINS_TO_REDIRECT[i]) !== -1) {
            return true;
        }
    }
    // Also match any *.easebar.com
    if (hostname.indexOf("easebar.com") !== -1) return true;
    if (hostname.indexOf("nie.netease.com") !== -1) return true;
    return false;
}

// Hook getaddrinfo in libc.so
var getaddrinfo = Module.findExportByName("libc.so", "getaddrinfo");
if (getaddrinfo) {
    Interceptor.attach(getaddrinfo, {
        onEnter: function(args) {
            this.node = args[0];
            this.res = args[3]; // struct addrinfo **res
            if (this.node.isNull()) return;
            
            var hostname = this.node.readUtf8String();
            if (hostname && shouldRedirect(hostname)) {
                console.log("[FRIDA-DNS] getaddrinfo(" + hostname + ") -> redirecting to " + TARGET_IP);
                this._redirect = true;
                this._hostname = hostname;
            } else {
                this._redirect = false;
            }
        },
        onLeave: function(retval) {
            if (!this._redirect) return;
            
            try {
                // Build a fake addrinfo result pointing to TARGET_IP
                var ai = Memory.alloc(64);
                var addr = Memory.alloc(16); // sockaddr_in
                var canonname = Memory.alloc(64);
                
                // sockaddr_in: family=AF_INET(2), port=0, addr=TARGET_IP
                addr.writeU16(2); // sin_family = AF_INET
                addr.writeU16(0); // sin_port = 0
                
                // Parse TARGET_IP into bytes
                var parts = TARGET_IP.split(".");
                for (var i = 0; i < 4; i++) {
                    addr.add(4 + i).writeU8(parseInt(parts[i]));
                }
                
                // Write hostname as canonname
                canonname.writeUtf8String(this._hostname);
                
                // addrinfo struct:
                // int ai_flags (0)
                // int ai_family (AF_INET = 2)
                // int ai_socktype (SOCK_STREAM = 1)
                // int ai_protocol (6 = IPPROTO_TCP)
                // socklen_t ai_addrlen (16)
                // struct sockaddr *ai_addr
                // char *ai_canonname
                // struct addrinfo *ai_next (NULL)
                ai.writeU32(0);          // ai_flags
                ai.add(4).writeU32(2);   // ai_family = AF_INET
                ai.add(8).writeU32(1);   // ai_socktype = SOCK_STREAM
                ai.add(12).writeU32(6);  // ai_protocol = IPPROTO_TCP
                ai.add(16).writeU32(16); // ai_addrlen = sizeof(sockaddr_in)
                ai.add(20).writePointer(addr);      // ai_addr
                ai.add(28).writePointer(canonname); // ai_canonname
                ai.add(36).writePointer(ptr(0));    // ai_next = NULL
                
                // Write result pointer
                this.res.writePointer(ai);
                
                // Return success (0 = EAI_SUCCESS)
                retval.replace(0);
                
                console.log("[FRIDA-DNS] getaddrinfo(" + this._hostname + ") -> " + TARGET_IP + " [OK]");
            } catch (e) {
                console.log("[FRIDA-DNS] ERROR: " + e);
            }
        }
    });
    console.log("[FRIDA-DNS] Hook installed on getaddrinfo @ " + getaddrinfo);
} else {
    console.log("[FRIDA-DNS] ERROR: getaddrinfo not found in libc.so");
}

// Also hook getaddrinfo from libclient.so if it has its own copy
try {
    var clientLib = Module.findBaseAddress("libclient.so");
    if (clientLib) {
        var exports = Module.enumerateExports("libclient.so");
        for (var i = 0; i < exports.length; i++) {
            if (exports[i].name.indexOf("getaddrinfo") !== -1 || 
                exports[i].name.indexOf("resolve") !== -1 ||
                exports[i].name.indexOf("dns") !== -1) {
                console.log("[FRIDA-DNS] Found in libclient.so: " + exports[i].name + " @ " + exports[i].address);
            }
        }
    }
} catch(e) {}

console.log("[FRIDA-DNS] Script loaded successfully");
