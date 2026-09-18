//@category ROS_RE
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

public class FindNewDictCallers extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_newdict_callers.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        // Find callers of EntityType::newDictionary (FUN_00a2a58c)
        Address target = toAddr(0x00a2a58cL);
        out.println("=== Callers of FUN_00a2a58c (EntityType::newDictionary) ===");
        ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(target);
        while (refs.hasNext()) {
            Reference r = refs.next();
            Address from = r.getFromAddress();
            Function callerFunc = getFunctionContaining(from);
            out.println("ref from " + from + " in function " + (callerFunc != null ? callerFunc.getName() + "@" + callerFunc.getEntryPoint() : "?"));
        }
        out.println();

        // Decompile the property-descriptor accessor functions
        long[] targets = {0x00ad0348L, 0x00ad02fcL, 0x00ad02ecL, 0x00ad0338L};
        for (long a : targets) {
            Address addr = toAddr(a);
            Function f = getFunctionAt(addr);
            out.println("=== " + (f != null ? f.getName() : "?") + " @ " + addr + " ===");
            if (f != null) {
                DecompileResults res = decomp.decompileFunction(f, 60, new ConsoleTaskMonitor());
                if (res != null && res.decompileCompleted()) {
                    out.println(res.getDecompiledFunction().getC());
                } else {
                    out.println("[decompile failed/timed out]");
                }
            } else {
                out.println("[no function at this address]");
            }
            out.println();
        }

        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
