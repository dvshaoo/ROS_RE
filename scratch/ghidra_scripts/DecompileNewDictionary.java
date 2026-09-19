//@category ROS_RE
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.address.Address;

import java.io.FileWriter;
import java.io.PrintWriter;

public class DecompileNewDictionary extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_newdict_settle.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));

        DecompInterface decomp = new DecompInterface();
        decomp.setOptions(new DecompileOptions());
        decomp.openProgram(currentProgram);

        // 00a2a58c = EntityType::newDictionary (per project notes)
        // 00acf5ec = the validity/type-check dispatcher Gemini cites for the property stream
        // 00a2ac04 = the wrapper called by ClientApp::onBasePlayerCreate with domain=0
        String[] targets = {"00a2a58c", "00acf5ec", "00a2ac04"};
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
                    out.println(res.getDecompiledFunction().getC());
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
