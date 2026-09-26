//@category ROS_RE
// "get_auth_type" appears exactly once as a native string in libclient.so
// (0x02b3c3a6) even though the Python-level ui/UILogin.py calls
// Globals.channel.get_auth_type() -- strong evidence this is a native
// PyMethodDef-style method table entry, i.e. Globals.channel is a
// native-bridged Python object, not a script.npk class. Dump every xref to
// this string and decompile the referencing function(s) to find the method
// table / registration site, plus its containing "channel" object's
// construction/init function.
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

public class FindAuthTypeXrefs extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_auth_type_xrefs.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        FunctionManager fm = currentProgram.getFunctionManager();
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        Address target = toAddr(0x02b3c3a6L);
        out.println("=== References TO \"get_auth_type\" @ " + target + " ===");
        ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(target);
        Set<Function> callers = new LinkedHashSet<>();
        while (refs.hasNext()) {
            Reference r = refs.next();
            Address from = r.getFromAddress();
            Function f = fm.getFunctionContaining(from);
            out.println("  ref from " + from + "  in function " + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "? (data-only ref, e.g. a static table entry)"));
            if (f != null) callers.add(f);
        }
        out.println();

        for (Function f : callers) {
            out.println("=== Decompile of caller: " + f.getName() + " @ " + f.getEntryPoint() + " ===");
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
