//@category ROS_RE
// Finds and decompiles the caller(s) of Bundle::iterator::unpack (FUN_00a83b24)
// to understand the loop that walks a packet's messages -- specifically how
// the iterator's position-tracking fields (offsets +4 and +10, read at the
// very start of unpack()) get initialized/advanced between calls, since
// that governs the "path A" (request ID + NRO) branch implicated in the
// still-unresolved "authenticate"/id-0 corruption bug.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.util.task.ConsoleTaskMonitor;

import java.io.FileWriter;
import java.io.PrintWriter;

public class FindUnpackCaller extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_unpack_caller.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        Address target = toAddr(0xa83b24L);
        out.println("=== Callers of Bundle::iterator::unpack (0xa83b24) ===");
        ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(target);
        int c = 0;
        while (refs.hasNext()) {
            Reference r = refs.next();
            Function f = currentProgram.getFunctionManager().getFunctionContaining(r.getFromAddress());
            out.println("  from " + r.getFromAddress() + " in " + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "UNKNOWN"));
            c++;
            if (f != null) {
                DecompileResults res = decomp.decompileFunction(f, 90, new ConsoleTaskMonitor());
                if (res != null && res.decompileCompleted()) {
                    out.println(res.getDecompiledFunction().getC());
                } else {
                    out.println("[decompile failed/timed out]");
                }
            }
            out.println();
        }
        if (c == 0) out.println("[no callers found]");

        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
