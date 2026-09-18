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

public class FindFilteredCallers extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_filtered_callers.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        Address target = toAddr(0xa8fa30L);
        out.println("=== References to Nub::processFilteredPacket (0xa8fa30) ===");
        ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(target);
        int c = 0;
        while (refs.hasNext()) {
            Reference r = refs.next();
            Function f = currentProgram.getFunctionManager().getFunctionContaining(r.getFromAddress());
            out.println("  from " + r.getFromAddress() + " in " + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "UNKNOWN") + " type=" + r.getReferenceType());
            c++;
            if (f != null && !f.getEntryPoint().equals(target)) {
                DecompileResults res = decomp.decompileFunction(f, 90, new ConsoleTaskMonitor());
                if (res != null && res.decompileCompleted()) {
                    String code = res.getDecompiledFunction().getC();
                    out.println(code.length() > 8000 ? code.substring(0, 8000) + "\n...[truncated]" : code);
                } else {
                    out.println("[decompile failed/timed out]");
                }
            }
            out.println();
        }
        if (c == 0) out.println("[no callers found]");

        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
