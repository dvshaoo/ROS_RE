//@category ROS_RE
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.util.task.ConsoleTaskMonitor;

import java.io.FileWriter;
import java.io.PrintWriter;

public class DecompileAdvance extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_advance.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        // FUN_00a83e28 (advance iterator?), FUN_00a83fac (has-more check),
        // FUN_00a83b10 (get current msgid), FUN_00a8b0c0 (header-length lookup
        // for a msgid, called from inside unpack itself)
        long[] targets = {0xa83e28L, 0xa83facL, 0xa83b10L, 0xa8b0c0L};
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
