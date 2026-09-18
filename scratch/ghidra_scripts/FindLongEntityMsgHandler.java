//@category ROS_RE
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

public class FindLongEntityMsgHandler extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_longentitymsg.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        String[] targets = {"longEntityMessage", "shortEntityMessage", "entityMessage"};
        for (String target : targets) {
            List<Address> stringAddrs = new ArrayList<>();
            DataIterator dataIt = currentProgram.getListing().getDefinedData(true);
            while (dataIt.hasNext()) {
                Data d = dataIt.next();
                if (d.hasStringValue()) {
                    Object v = d.getValue();
                    if (v != null && v.toString().equals(target)) {
                        stringAddrs.add(d.getAddress());
                    }
                }
            }
            out.println("=== \"" + target + "\": " + stringAddrs.size() + " string(s) ===");
            for (Address strAddr : stringAddrs) {
                out.println("string @ " + strAddr);
                ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(strAddr);
                int c = 0;
                while (refs.hasNext()) {
                    Reference r = refs.next();
                    Address from = r.getFromAddress();
                    Function f = currentProgram.getFunctionManager().getFunctionContaining(from);
                    out.println("  ref from " + from + " in " + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "UNKNOWN"));
                    c++;
                    if (f != null && c <= 3) {
                        DecompileResults res = decomp.decompileFunction(f, 45, new ConsoleTaskMonitor());
                        if (res != null && res.decompileCompleted()) {
                            out.println(res.getDecompiledFunction().getC());
                        }
                    }
                }
                if (c == 0) out.println("  [no references found]");
            }
            out.println();
        }

        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
