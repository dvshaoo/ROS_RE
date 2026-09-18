//@category ROS_RE
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.util.task.ConsoleTaskMonitor;

import java.io.FileWriter;
import java.io.PrintWriter;

public class DecompilePropStream extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_propstream.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        // Candidate Ghidra-space addresses for the "0x9cf8ac" static-space
        // property-stream unpack function referenced in
        // 06_notes/GHIDRA_PACKET_PARSER_TRACE.md (EntityType::newDictionary,
        // non-empty-stream branch). This project's established offset from
        // static address to Ghidra loaded address is +0x100000 (confirmed via
        // 0x918504 static -> 0x00a18504 Ghidra for ClientApp::onBasePlayerCreate).
        long[] targets = {0x00acf8acL, 0x009cf8acL, 0x00a2a58cL};
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
