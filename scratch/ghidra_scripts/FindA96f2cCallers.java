//@category ROS_RE
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

import java.io.FileWriter;
import java.io.PrintWriter;

public class FindA96f2cCallers extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_a96f2c_callers.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        Address targetAddr = toAddr(0xa96f2cL);
        out.println("=== References to 0xa96f2c ===");
        for (Reference ref : getReferencesTo(targetAddr)) {
            Address fromAddr = ref.getFromAddress();
            Function f = getFunctionContaining(fromAddr);
            out.println("  from " + fromAddr + " in " + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "UNKNOWN") + " type=" + ref.getReferenceType());
        }
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
