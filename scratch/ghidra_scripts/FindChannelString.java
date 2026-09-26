//@category ROS_RE
// Locates the exact string literals "channel" and "get_auth_type" (used by
// ui/UILogin.py's Globals.channel.get_auth_type() call, whose source we
// could not find anywhere in script.npk -- suggesting Globals.channel is a
// native-bridged Python object, not a pure script class). Lists every
// defined-data occurrence and, for "channel", every cross-reference plus
// the containing function name, so we can pick decompile targets next.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.LinkedHashSet;
import java.util.Set;

public class FindChannelString extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_channel_strings.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        FunctionManager fm = currentProgram.getFunctionManager();

        String[] targets = { "channel", "get_auth_type", "Globals", "netease_global" };

        DataIterator dataIt = currentProgram.getListing().getDefinedData(true);
        int total = 0;
        java.util.Map<String, java.util.List<Address>> hits = new java.util.LinkedHashMap<>();
        for (String t : targets) hits.put(t, new java.util.ArrayList<Address>());

        while (dataIt.hasNext()) {
            Data d = dataIt.next();
            if (d.hasStringValue()) {
                String s = d.getValue().toString();
                for (String t : targets) {
                    if (s.equals(t)) {
                        hits.get(t).add(d.getAddress());
                        total++;
                    }
                }
            }
        }

        for (String t : targets) {
            out.println("=== exact string \"" + t + "\": " + hits.get(t).size() + " occurrence(s) ===");
            for (Address a : hits.get(t)) {
                out.println("  " + a);
            }
        }
        out.println();
        out.println("Total exact-match strings found: " + total);
        out.println();

        // For "channel" specifically, dump xrefs + calling function names (most useful lead).
        for (Address a : hits.get("channel")) {
            out.println("--- xrefs to \"channel\" @ " + a + " ---");
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(a);
            Set<String> seen = new LinkedHashSet<>();
            while (refs.hasNext()) {
                Reference r = refs.next();
                Address from = r.getFromAddress();
                Function f = fm.getFunctionContaining(from);
                String line = "  ref from " + from + "  in function " + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "?");
                if (seen.add(line)) out.println(line);
            }
            out.println();
        }

        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
