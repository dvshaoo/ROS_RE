//@category ROS_RE
// Instead of dumping full (huge) decompiled pseudocode for the 3 callers of
// FUN_00a473d0, list the string literals each caller function references --
// BigWorld binaries tend to have descriptive log/assert strings (as seen
// with LoginHandler::onLoginReply) that reveal a function's real purpose
// far faster than reading raw pseudocode of a multi-KB function.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;

import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.LinkedHashSet;
import java.util.Set;

public class CallerStrings extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_caller_strings.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));

        long[] callerAddrs = {0x93d110L, 0x93a558L, 0x94d4a0L};
        for (long a : callerAddrs) {
            Address addr = toAddr(a);
            Function f = getFunctionAt(addr);
            if (f == null) f = currentProgram.getFunctionManager().getFunctionContaining(addr);
            out.println("=== Function containing " + addr + ": "
                    + (f != null ? f.getName() + " @ " + f.getEntryPoint() + " size=" + f.getBody().getNumAddresses() : "UNKNOWN") + " ===");
            if (f == null) { out.println(); continue; }

            Set<String> strs = new LinkedHashSet<>();
            for (Instruction instr : currentProgram.getListing().getInstructions(f.getBody(), true)) {
                for (Reference r : instr.getReferencesFrom()) {
                    Data d = getDataAt(r.getToAddress());
                    if (d != null && d.hasStringValue()) {
                        strs.add(d.getValue().toString());
                    }
                }
            }
            out.println("String literals referenced (" + strs.size() + "):");
            for (String s : strs) {
                String trimmed = s.length() > 200 ? s.substring(0, 200) + "...[truncated]" : s;
                out.println("  \"" + trimmed + "\"");
            }
            out.println();
        }
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
