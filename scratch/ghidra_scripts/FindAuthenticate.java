//@category ROS_RE
// Finds the "authenticate" string in the binary and all code/data references
// to it, to understand what real exposed-method registration it belongs to
// (its declared msgID, argument count/types, FIXED vs VARIABLE length) --
// needed to resolve the live "Bundle::iterator::unpack( authenticate ): Not
// enough data on stream" corruption bug that has resisted several rounds of
// live bisection (see GHIDRA_ONCHANNELLOGIN_TRACE.md Finding 6/7).
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
import java.util.ArrayList;
import java.util.List;

public class FindAuthenticate extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_authenticate.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        // Find all string data whose value is exactly "authenticate"
        List<Address> stringAddrs = new ArrayList<>();
        DataIterator dataIt = currentProgram.getListing().getDefinedData(true);
        while (dataIt.hasNext()) {
            Data d = dataIt.next();
            if (d.hasStringValue()) {
                Object v = d.getValue();
                if (v != null && v.toString().equals("authenticate")) {
                    stringAddrs.add(d.getAddress());
                }
            }
        }
        out.println("Found " + stringAddrs.size() + " string(s) matching exactly \"authenticate\"");
        for (Address a : stringAddrs) out.println("  " + a);
        out.println();

        for (Address strAddr : stringAddrs) {
            out.println("=== References to \"authenticate\" @ " + strAddr + " ===");
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(strAddr);
            int c = 0;
            while (refs.hasNext()) {
                Reference r = refs.next();
                Address from = r.getFromAddress();
                Function f = currentProgram.getFunctionManager().getFunctionContaining(from);
                out.println("  from " + from + " in " + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "UNKNOWN"));
                c++;
                if (f != null && c <= 5) {
                    DecompileResults res = decomp.decompileFunction(f, 45, new ConsoleTaskMonitor());
                    if (res != null && res.decompileCompleted()) {
                        out.println(res.getDecompiledFunction().getC());
                    }
                }
            }
            if (c == 0) out.println("  [no references found]");
            out.println();
        }

        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
