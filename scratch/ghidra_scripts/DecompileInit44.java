//@category ROS_RE
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.util.task.ConsoleTaskMonitor;

import java.io.FileWriter;
import java.io.PrintWriter;

public class DecompileInit44 extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_init44.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        Address addr = toAddr(0x0090c5a0L);
        Function f = getFunctionAt(addr);
        out.println("=== " + (f != null ? f.getName() : "?") + " @ " + addr + " ===");
        if (f != null) {
            DecompileResults res = decomp.decompileFunction(f, 120, new ConsoleTaskMonitor());
            if (res != null && res.decompileCompleted()) {
                out.println(res.getDecompiledFunction().getC());
            } else {
                out.println("[decompile failed/timed out]");
            }
        }
        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
