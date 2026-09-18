//@category ROS_RE
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.util.task.ConsoleTaskMonitor;

import java.io.FileWriter;
import java.io.PrintWriter;

public class FindDatXrefs extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_dat_af50_xrefs.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        FunctionManager fm = currentProgram.getFunctionManager();
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        Address target = toAddr(0x00467af50L);
        out.println("=== References TO " + target + " (identifyVersionPoint InterfaceElement) ===");
        ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(target);
        java.util.Set<Function> callers = new java.util.LinkedHashSet<>();
        while (refs.hasNext()) {
            Reference r = refs.next();
            Address from = r.getFromAddress();
            Function f = fm.getFunctionContaining(from);
            out.println("  ref from " + from + "  in function " + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "?"));
            if (f != null) callers.add(f);
        }
        out.println();

        for (Function f : callers) {
            if (f.getName().equals("_INIT_44")) continue; // skip the init/registration site itself
            out.println("=== Decompile of caller: " + f.getName() + " @ " + f.getEntryPoint() + " ===");
            DecompileResults res = decomp.decompileFunction(f, 60, new ConsoleTaskMonitor());
            if (res != null && res.decompileCompleted()) {
                out.println(res.getDecompiledFunction().getC());
            } else {
                out.println("[decompile failed/timed out]");
            }
            out.println();
        }

        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
