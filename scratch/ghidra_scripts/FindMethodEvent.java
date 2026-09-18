//@category ROS_RE
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.util.task.ConsoleTaskMonitor;

import java.io.FileWriter;
import java.io.PrintWriter;

public class FindMethodEvent extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_baseplayer.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        FunctionManager fm = currentProgram.getFunctionManager();
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        // 0x918504 -> in Ghidra with 0x100000 ELF base: 0x00918504 or 0x00a18504?
        // Wait, libclient ELF image base:
        // Let's check entry points around 0x00918504 and 0x00a18504
        Function f = fm.getFunctionAt(toAddr(0x00a18504L));
        if (f == null) f = fm.getFunctionAt(toAddr(0x00918504L));
        if (f == null) f = fm.getFunctionContaining(toAddr(0x00a18504L));
        if (f == null) f = fm.getFunctionContaining(toAddr(0x00918504L));

        out.println("Function found: " + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "null"));
        if (f != null) {
            DecompileResults res = decomp.decompileFunction(f, 60, new ConsoleTaskMonitor());
            if (res != null && res.decompileCompleted()) {
                out.println(res.getDecompiledFunction().getC());
            }
        }

        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
