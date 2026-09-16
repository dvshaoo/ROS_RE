// Deep140.java
// Inspects the vtable-slot context for the entity+0x140 SETTER (FUN_00a3a5e4,
// static 0x93a5e4) found at data ref 0x33f4a80, and fully decompiles
// FUN_009473d0 (static 0x9473d0, called from the setter, touches +0x138/
// +0x150) to understand the full state-transition chain around the gate.
//@category ROS_RE

import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolTable;
import ghidra.util.task.ConsoleTaskMonitor;

import java.io.FileWriter;
import java.io.PrintWriter;

public class Deep140 extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_deep140.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        long imageBase = currentProgram.getImageBase().getOffset();
        SymbolTable st = currentProgram.getSymbolTable();
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        out.println("=== Context around setter's vtable slot 0x33f4a80 ===");
        Address slot = toAddr(0x33f4a80L);
        for (long back = 8; back <= 64; back += 8) {
            Address p = slot.subtract(back);
            for (Symbol s : st.getSymbols(p)) {
                out.println("  -" + back + ": " + p + " " + s.getName() + " [" + s.getSymbolType() + "]");
            }
        }
        out.println("  --- references TO the slot address itself ---");
        ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(slot);
        int c = 0;
        while (refs.hasNext() && c < 20) {
            Reference r = refs.next();
            out.println("    from " + r.getFromAddress() + " type=" + r.getReferenceType());
            c++;
        }
        if (c == 0) out.println("    [none]");
        out.println();

        long[] targets = {0x9473d0L};
        for (long so : targets) {
            Address a = toAddr(imageBase + so);
            Function f = getFunctionAt(a);
            if (f == null) f = currentProgram.getFunctionManager().getFunctionContaining(a);
            out.println("=== Decompile 0x" + Long.toHexString(so) + " -> " + a + " (" + (f != null ? f.getName() : "none") + ") ===");
            if (f != null) {
                DecompileResults res = decomp.decompileFunction(f, 60, new ConsoleTaskMonitor());
                if (res != null && res.decompileCompleted()) {
                    out.println(res.getDecompiledFunction().getC());
                } else {
                    out.println("  [decompile failed: " + (res != null ? res.getErrorMessage() : "null") + "]");
                }
                out.println("  --- callers ---");
                ReferenceIterator r2 = currentProgram.getReferenceManager().getReferencesTo(f.getEntryPoint());
                int cc = 0;
                while (r2.hasNext()) {
                    Reference r = r2.next();
                    out.println("    from " + r.getFromAddress() + " type=" + r.getReferenceType());
                    cc++;
                }
                if (cc == 0) out.println("    [none]");
            }
            out.println();
        }

        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
