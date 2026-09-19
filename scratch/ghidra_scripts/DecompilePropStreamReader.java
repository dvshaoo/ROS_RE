//@category ROS_RE
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.address.Address;

import java.io.FileWriter;
import java.io.PrintWriter;

public class DecompilePropStreamReader extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_propstream_reader.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));

        DecompInterface decomp = new DecompInterface();
        DecompileOptions opts = new DecompileOptions();
        decomp.setOptions(opts);
        decomp.openProgram(currentProgram);

        // 00acf8ac = the real property-stream deserializer (entityType, stream, flagMask, dict)
        // 00acf5ec = the per-property flag/domain match predicate it uses
        // 00a9f8e4 = per-property value reader referenced by the notes
        String[] targets = {"00acf8ac", "00acf5ec", "00a9f8e4"};
        for (String t : targets) {
            Address entry = currentProgram.getAddressFactory().getAddress(t);
            Function f = currentProgram.getFunctionManager().getFunctionAt(entry);
            if (f == null) f = currentProgram.getFunctionManager().getFunctionContaining(entry);
            out.println("=================================================================");
            out.println("=== " + t + " -> " + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "NOT FOUND") + " ===");
            out.println("=================================================================");
            if (f != null) {
                DecompileResults res = decomp.decompileFunction(f, 400, new ghidra.util.task.ConsoleTaskMonitor());
                if (res != null && res.decompileCompleted()) {
                    // strip Ghidra's noisy catch() comment lines to keep the output readable
                    String c = res.getDecompiledFunction().getC();
                    for (String line : c.split("\n")) {
                        if (line.trim().startsWith("/* catch()") || line.trim().startsWith("/* try {")) continue;
                        out.println(line);
                    }
                } else {
                    out.println("Decompile failed: " + (res != null ? res.getErrorMessage() : "null"));
                }
            }
            out.println();
        }

        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
