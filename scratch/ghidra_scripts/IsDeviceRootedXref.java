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

public class IsDeviceRootedXref extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_isdevicerooted.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        Address strAddr = toAddr(0x2cd51e0L);
        out.println("=== References to string \"isDeviceRooted\" @ " + strAddr + " ===");
        ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(strAddr);
        int c = 0;
        while (refs.hasNext()) {
            Reference r = refs.next();
            Address from = r.getFromAddress();
            Function f = currentProgram.getFunctionManager().getFunctionContaining(from);
            out.println("  from " + from + " in function " + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "UNKNOWN"));
            c++;
            if (f != null) {
                DecompileResults res = decomp.decompileFunction(f, 60, new ConsoleTaskMonitor());
                if (res != null && res.decompileCompleted()) {
                    out.println(res.getDecompiledFunction().getC());
                }
                out.println("  --- callers of " + f.getName() + " ---");
                ReferenceIterator r2 = currentProgram.getReferenceManager().getReferencesTo(f.getEntryPoint());
                int cc = 0;
                while (r2.hasNext()) {
                    Reference rr = r2.next();
                    out.println("    from " + rr.getFromAddress() + " type=" + rr.getReferenceType());
                    cc++;
                }
                if (cc == 0) out.println("    [none -- virtual dispatch]");
            }
            out.println();
        }
        out.println("Total refs: " + c);
        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
