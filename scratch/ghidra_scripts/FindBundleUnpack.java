//@category ROS_RE
// Finds the "Not enough data on stream" / "Bundle::iterator::unpack" log
// string(s) and decompiles the containing function(s) in full, to determine
// EXACTLY how the client decides where one message in a received datagram
// ends and whether/how it looks for a next one -- needed to resolve the
// live "authenticate"/id-0 corruption bug that has resisted several rounds
// of live packet-content bisection (see GHIDRA_ONCHANNELLOGIN_TRACE.md and
// CLIENTINTERFACE_MESSAGE_TABLE.md).
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.util.task.ConsoleTaskMonitor;

import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.LinkedHashSet;
import java.util.Set;

public class FindBundleUnpack extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_bundle_unpack.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        String[] needles = {
            "Not enough data on stream",
            "Got corrupted message header",
            "Discarding bundle due to corrupted header"
        };

        Set<Address> containingFuncs = new LinkedHashSet<>();
        DataIterator dataIt = currentProgram.getListing().getDefinedData(true);
        while (dataIt.hasNext()) {
            Data d = dataIt.next();
            if (!d.hasStringValue()) continue;
            String s = d.getValue().toString();
            boolean match = false;
            for (String n : needles) {
                if (s.contains(n)) { match = true; break; }
            }
            if (!match) continue;

            out.println("=== String @ " + d.getAddress() + ": \"" +
                    (s.length() > 100 ? s.substring(0, 100) + "..." : s) + "\" ===");
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(d.getAddress());
            while (refs.hasNext()) {
                Reference r = refs.next();
                Function f = currentProgram.getFunctionManager().getFunctionContaining(r.getFromAddress());
                if (f != null) {
                    out.println("  referenced from " + r.getFromAddress() + " in " + f.getName() + " @ " + f.getEntryPoint());
                    containingFuncs.add(f.getEntryPoint());
                }
            }
            out.println();
        }

        out.println("=== Decompiling " + containingFuncs.size() + " unique containing function(s) ===");
        for (Address entry : containingFuncs) {
            Function f = getFunctionAt(entry);
            out.println("--- " + (f != null ? f.getName() : "?") + " @ " + entry + " ---");
            if (f != null) {
                DecompileResults res = decomp.decompileFunction(f, 90, new ConsoleTaskMonitor());
                if (res != null && res.decompileCompleted()) {
                    out.println(res.getDecompiledFunction().getC());
                } else {
                    out.println("[decompile failed/timed out]");
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
