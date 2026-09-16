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

public class CallSites473d0 extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_callsites_473d0.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        long[] callerAddrs = {0x93d110L, 0x93a558L, 0x94d4a0L}; // already runtime (imageBase-included) addrs
        for (long a : callerAddrs) {
            Address addr = toAddr(a);
            Function f = getFunctionAt(addr);
            if (f == null) f = currentProgram.getFunctionManager().getFunctionContaining(addr);
            out.println("=== Caller site " + addr + " in function " + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "UNKNOWN") + " ===");
            if (f != null) {
                DecompileResults res = decomp.decompileFunction(f, 60, new ConsoleTaskMonitor());
                if (res != null && res.decompileCompleted()) {
                    out.println(res.getDecompiledFunction().getC());
                } else {
                    out.println("  [decompile failed]");
                }
                out.println("  --- callers of " + f.getName() + " ---");
                ReferenceIterator r2 = currentProgram.getReferenceManager().getReferencesTo(f.getEntryPoint());
                int cc = 0;
                while (r2.hasNext()) {
                    Reference r = r2.next();
                    out.println("    from " + r.getFromAddress() + " type=" + r.getReferenceType());
                    cc++;
                }
                if (cc == 0) out.println("    [none -- reached via virtual dispatch]");
            }
            out.println();
        }
        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
