//@category ROS_RE
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.util.task.ConsoleTaskMonitor;

import java.io.FileWriter;
import java.io.PrintWriter;

public class FindVersionPointRefs extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_versionpoint_refs.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        Memory mem = currentProgram.getMemory();

        byte[] needle1 = "identifyVersionPoint".getBytes("ascii");
        byte[] needle2 = "summariseVersionPoint".getBytes("ascii");

        Address found1 = mem.findBytes(mem.getMinAddress(), needle1, null, true, monitor);
        Address found2 = mem.findBytes(mem.getMinAddress(), needle2, null, true, monitor);
        out.println("identifyVersionPoint string @ " + found1);
        out.println("summariseVersionPoint string @ " + found2);
        out.println();

        FunctionManager fm = currentProgram.getFunctionManager();

        for (Address strAddr : new Address[]{found1, found2}) {
            if (strAddr == null) continue;
            out.println("=== References TO " + strAddr + " ===");
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(strAddr);
            while (refs.hasNext()) {
                Reference r = refs.next();
                Address from = r.getFromAddress();
                Function f = fm.getFunctionContaining(from);
                out.println("  ref from " + from + "  in function " + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "?"));
            }
            out.println();
        }

        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
