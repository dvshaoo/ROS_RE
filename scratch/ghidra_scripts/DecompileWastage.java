//@category ROS_RE
// Decompiles the wastage-byte consumer this project's E2E-020 static
// analysis found at static offset 0x989324-0x989350, to determine whether
// it runs BEFORE Bundle::iterator::unpack sees the buffer (stripping our
// padding first, as this session's code assumed) or AFTER/never for this
// path -- the open question from GHIDRA_ONCHANNELLOGIN_TRACE.md Finding 7.
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

public class DecompileWastage extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_wastage.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        long imageBase = currentProgram.getImageBase().getOffset();
        long[] targets = {0x989324L, 0x9892c8L};
        for (long so : targets) {
            Address a = toAddr(imageBase + so);
            Function f = getFunctionAt(a);
            if (f == null) f = currentProgram.getFunctionManager().getFunctionContaining(a);
            out.println("=== static 0x" + Long.toHexString(so) + " -> " + a + " (" + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "no func") + ") ===");
            if (f != null) {
                DecompileResults res = decomp.decompileFunction(f, 60, new ConsoleTaskMonitor());
                if (res != null && res.decompileCompleted()) {
                    out.println(res.getDecompiledFunction().getC());
                } else {
                    out.println("[decompile failed/timed out]");
                }
                out.println("--- callers of " + f.getName() + " ---");
                ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(f.getEntryPoint());
                int c = 0;
                while (refs.hasNext()) {
                    Reference r = refs.next();
                    Function cf = currentProgram.getFunctionManager().getFunctionContaining(r.getFromAddress());
                    out.println("  from " + r.getFromAddress() + " in " + (cf != null ? cf.getName() + " @ " + cf.getEntryPoint() : "?") + " type=" + r.getReferenceType());
                    c++;
                }
                if (c == 0) out.println("  [none -- virtual dispatch]");
            }
            out.println();
        }

        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
