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

public class RootCheckCaller extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_rootcheck_caller.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        Address a = toAddr(0x1ceef9cL);
        Function f = currentProgram.getFunctionManager().getFunctionContaining(a);
        out.println("Caller function: " + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "UNKNOWN"));
        if (f != null) {
            DecompileResults res = decomp.decompileFunction(f, 60, new ConsoleTaskMonitor());
            if (res != null && res.decompileCompleted()) {
                out.println(res.getDecompiledFunction().getC());
            } else {
                out.println("[decompile failed]");
            }
            out.println("--- callers of " + f.getName() + " ---");
            ReferenceIterator r2 = currentProgram.getReferenceManager().getReferencesTo(f.getEntryPoint());
            int cc = 0;
            while (r2.hasNext()) {
                Reference rr = r2.next();
                out.println("  from " + rr.getFromAddress() + " type=" + rr.getReferenceType());
                cc++;
            }
            if (cc == 0) out.println("  [none -- virtual dispatch]");
        }
        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
