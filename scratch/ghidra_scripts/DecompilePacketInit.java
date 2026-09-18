//@category ROS_RE
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.util.task.ConsoleTaskMonitor;

import java.io.FileWriter;
import java.io.PrintWriter;

public class DecompilePacketInit extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_packet_init.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        long[] addrs = {0xa96978L, 0xa96a14L, 0xa8ccfcL, 0xa8d380L};
        for (long a : addrs) {
            Address addr = toAddr(a);
            Function f = getFunctionAt(addr);
            out.println("=== " + (f != null ? f.getName() : "?") + " @ " + addr + " ===");
            if (f != null) {
                DecompileResults res = decomp.decompileFunction(f, 60, new ConsoleTaskMonitor());
                if (res != null && res.decompileCompleted()) {
                    out.println(res.getDecompiledFunction().getC());
                } else {
                    out.println("[decompile failed: " + (res != null ? res.getErrorMessage() : "null") + "]");
                }
            }
            out.println("\n--------------------------------------------------\n");
        }
        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
