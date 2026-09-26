//@category ROS_RE
// Decompiles get_auth_type (FUN_00973ffc), get_auth_type_name (FUN_00974020),
// and guest_bind (FUN_009740f8) -- native PyMethodDef-table methods on the
// object exposed to Python as Globals.channel (com.netease.chiji's private
// server, Checkpoint 26 "Link Account" investigation). Also decompiles
// whatever function CONTAINS the method table at 0x03a1a5c0 (the class's
// registration/init site) to find when/how this object becomes ready.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.util.task.ConsoleTaskMonitor;

import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.LinkedHashSet;
import java.util.Set;

public class DecompileAuthType extends GhidraScript {
    private void decompileAt(PrintWriter out, DecompInterface decomp, FunctionManager fm, long addr, String label) {
        Address a = toAddr(addr);
        Function f = fm.getFunctionAt(a);
        if (f == null) f = fm.getFunctionContaining(a);
        out.println("=== " + label + ": " + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "no function at " + a) + " ===");
        if (f != null) {
            DecompileResults res = decomp.decompileFunction(f, 60, new ConsoleTaskMonitor());
            if (res != null && res.decompileCompleted()) {
                out.println(res.getDecompiledFunction().getC());
            } else {
                out.println("[decompile failed/timed out]");
            }
        }
        out.println();
    }

    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_authtype_decompile.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        FunctionManager fm = currentProgram.getFunctionManager();
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        decompileAt(out, decomp, fm, 0x00973ffcL, "get_auth_type");
        decompileAt(out, decomp, fm, 0x00974020L, "get_auth_type_name");
        decompileAt(out, decomp, fm, 0x009740f8L, "guest_bind");

        // Who references the method table itself (0x03a1a5c0), i.e. who registers/builds this class?
        Address tableAddr = toAddr(0x03a1a5c0L);
        out.println("=== References TO method table @ " + tableAddr + " ===");
        ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(tableAddr);
        Set<Function> callers = new LinkedHashSet<>();
        while (refs.hasNext()) {
            Reference r = refs.next();
            Address from = r.getFromAddress();
            Function f = fm.getFunctionContaining(from);
            out.println("  ref from " + from + "  in function " + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "?"));
            if (f != null) callers.add(f);
        }
        out.println();
        for (Function f : callers) {
            out.println("=== Decompile of table-referencing function: " + f.getName() + " @ " + f.getEntryPoint() + " ===");
            DecompileResults res = decomp.decompileFunction(f, 60, new ConsoleTaskMonitor());
            if (res != null && res.decompileCompleted()) {
                out.println(res.getDecompiledFunction().getC());
            } else {
                out.println("[decompile failed/timed out]");
            }
            out.println();
        }

        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
