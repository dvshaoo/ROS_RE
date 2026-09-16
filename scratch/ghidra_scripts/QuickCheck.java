//@category ROS_RE
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.util.task.ConsoleTaskMonitor;
import java.io.FileWriter;
import java.io.PrintWriter;

public class QuickCheck extends GhidraScript {
    @Override
    protected void run() throws Exception {
        PrintWriter out = new PrintWriter(new FileWriter("C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_quickcheck.txt", false));
        long imageBase = currentProgram.getImageBase().getOffset();
        out.println("imageBase=0x" + Long.toHexString(imageBase));

        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        long[] offsets = {0x938070L, 0x94c540L, 0x989600L, 0x98924cL};
        for (long off : offsets) {
            Address a1 = toAddr(off + imageBase);
            out.println("--- offset 0x" + Long.toHexString(off) + " -> imageBase+offset = " + a1 + " ---");
            Function f = getFunctionAt(a1);
            if (f == null) f = currentProgram.getFunctionManager().getFunctionContaining(a1);
            if (f != null) {
                out.println("  Function: " + f.getName() + " @ " + f.getEntryPoint());
                DecompileResults res = decomp.decompileFunction(f, 30, new ConsoleTaskMonitor());
                if (res != null && res.decompileCompleted()) {
                    out.println(res.getDecompiledFunction().getC());
                }
            } else {
                out.println("  [no function]");
            }
        }
        decomp.dispose();
        out.flush();
        out.close();
        println("done");
    }
}
