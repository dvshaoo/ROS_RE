//@category ROS_RE
// Dumps raw 8-byte words around the data-only xref to "get_auth_type"
// (0x03a1a640) to identify the PyMethodDef-style table it belongs to
// (typically {char* name; void* func; int flags; char* doc;} on a 64-bit
// target), and resolves each pointer-looking word to a symbol/string/
// function if Ghidra already knows what's there.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Data;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolTable;

import java.io.FileWriter;
import java.io.PrintWriter;

public class DumpAuthTypeTable extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_authtype_table.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        Memory mem = currentProgram.getMemory();
        SymbolTable st = currentProgram.getSymbolTable();

        Address center = toAddr(0x03a1a640L);
        // dump from 128 bytes before to 128 bytes after, 8 bytes at a time
        Address start = center.subtract(128);
        for (int i = 0; i < 32; i++) {
            Address a = start.add(i * 8L);
            long val;
            try {
                val = mem.getLong(a);
            } catch (Exception e) {
                out.println(a + ": <unreadable>");
                continue;
            }
            String marker = a.equals(center) ? "  <== get_auth_type string ptr found here" : "";
            String resolved = "";
            try {
                Address target = toAddr(val);
                Data d = getDataAt(target);
                if (d != null && d.hasStringValue()) {
                    resolved = "  -> string \"" + d.getValue().toString() + "\"";
                } else {
                    Function f = getFunctionAt(target);
                    if (f != null) {
                        resolved = "  -> function " + f.getName() + " @ " + f.getEntryPoint();
                    } else {
                        Symbol[] syms = st.getSymbols(target);
                        if (syms.length > 0) {
                            resolved = "  -> symbol " + syms[0].getName();
                        }
                    }
                }
            } catch (Exception e) {
                // val isn't a valid address; leave resolved blank
            }
            out.println(a + ": 0x" + Long.toHexString(val) + resolved + marker);
        }

        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
