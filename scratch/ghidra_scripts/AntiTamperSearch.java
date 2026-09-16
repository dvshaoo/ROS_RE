//@category ROS_RE
// Searches all defined strings in the binary for anti-tamper / root-
// detection / anti-frida markers, to test the hypothesis (raised in
// GHIDRA_ONCHANNELLOGIN_TRACE.md Finding 5) that the BaseApp-channel
// blocker is caused by a runtime environment check rather than a protocol
// bug.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;

import java.io.FileWriter;
import java.io.PrintWriter;

public class AntiTamperSearch extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_antitamper_strings.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));

        String[] keywords = {
            "frida", "xposed", "magisk", "su\0", "/system/xbin/su", "/system/bin/su",
            "ptrace", "root", "riru", "substrate", "gadget", "linjector",
            "TracerPid", "/proc/self/maps", "gum-js-loop", "re.frida"
        };

        DataIterator dataIt = currentProgram.getListing().getDefinedData(true);
        int found = 0;
        while (dataIt.hasNext()) {
            Data d = dataIt.next();
            if (d.hasStringValue()) {
                String s = d.getValue().toString();
                String sLower = s.toLowerCase();
                for (String kw : keywords) {
                    if (sLower.contains(kw.toLowerCase())) {
                        String trimmed = s.length() > 150 ? s.substring(0, 150) + "...[truncated]" : s;
                        out.println(d.getAddress() + "  \"" + trimmed + "\"");
                        found++;
                        break;
                    }
                }
            }
        }
        out.println("Total matches: " + found);
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
