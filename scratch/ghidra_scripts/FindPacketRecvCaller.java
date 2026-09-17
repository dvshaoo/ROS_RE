//@category ROS_RE
// Finds and decompiles the caller(s) of Nub::processPacket (FUN_00a90b14),
// to trace back to where the raw UDP payload first gets wrapped into a
// "chain link" packet structure (fields at +0x1a=length, +0x1c, +0x10=next,
// +0x60=data start) that Bundle::iterator::unpack later reads. This is the
// missing piece needed to confirm what "total_chain_length" is actually
// derived from for our own sent packets, per GHIDRA_ONCHANNELLOGIN_TRACE.md
// Finding 8's open item.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.util.task.ConsoleTaskMonitor;

import java.io.FileWriter;
import java.io.PrintWriter;

public class FindPacketRecvCaller extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_packetrecv_caller.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        Address target = toAddr(0xa90b14L);
        out.println("=== Callers of Nub::processPacket (0xa90b14) ===");
        ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(target);
        int c = 0;
        while (refs.hasNext()) {
            Reference r = refs.next();
            Function f = currentProgram.getFunctionManager().getFunctionContaining(r.getFromAddress());
            out.println("  from " + r.getFromAddress() + " in " + (f != null ? f.getName() + " @ " + f.getEntryPoint() : "UNKNOWN") + " type=" + r.getReferenceType());
            c++;
            if (f != null) {
                DecompileResults res = decomp.decompileFunction(f, 90, new ConsoleTaskMonitor());
                if (res != null && res.decompileCompleted()) {
                    String code = res.getDecompiledFunction().getC();
                    out.println(code.length() > 6000 ? code.substring(0, 6000) + "\n...[truncated]" : code);
                } else {
                    out.println("[decompile failed/timed out]");
                }
            }
            out.println();
        }
        if (c == 0) out.println("[no callers found]");

        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
