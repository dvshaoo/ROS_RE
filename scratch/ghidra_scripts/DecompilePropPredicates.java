//@category ROS_RE
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.address.Address;

import java.io.FileWriter;
import java.io.PrintWriter;

public class DecompilePropPredicates extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_prop_predicates.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));

        DecompInterface decomp = new DecompInterface();
        decomp.setOptions(new DecompileOptions());
        decomp.openProgram(currentProgram);
        Listing listing = currentProgram.getListing();

        // the three gating predicates in FUN_00acf5ec, plus the two skipped ones,
        // plus the visitor's own visit() implementation at PTR_FUN_038e07b8 + 0x10
        String[] targets = {"00a9f2e0", "00aa0cec", "00a9f2ec", "00a9f2d4", "00aa0cf8"};
        for (String t : targets) {
            Address entry = currentProgram.getAddressFactory().getAddress(t);
            Function f = currentProgram.getFunctionManager().getFunctionAt(entry);
            if (f == null) f = currentProgram.getFunctionManager().getFunctionContaining(entry);
            out.println("=== " + t + " -> " + (f != null ? f.getName() : "NOT FOUND") + " ===");
            if (f != null) {
                DecompileResults res = decomp.decompileFunction(f, 200, new ghidra.util.task.ConsoleTaskMonitor());
                if (res != null && res.decompileCompleted()) {
                    out.println(res.getDecompiledFunction().getC());
                }
                out.println("  -- disasm --");
                Instruction ins = listing.getInstructionAt(f.getEntryPoint());
                for (int i = 0; i < 14 && ins != null; i++) {
                    out.println(String.format("    %s  %s", ins.getAddress(), ins.toString()));
                    ins = ins.getNext();
                }
            }
            out.println();
        }

        // the visitor vtable: slot 0x10 is visit(desc) -- the thing that reads the stream
        Address vt = currentProgram.getAddressFactory().getAddress("038e07b8");
        out.println("=== visitor vtable @ 038e07b8 ===");
        for (int i = 0; i < 6; i++) {
            Address slot = vt.add(i * 8L);
            long val = currentProgram.getMemory().getLong(slot);
            Address tgt = currentProgram.getAddressFactory().getAddress(Long.toHexString(val));
            Function tf = currentProgram.getFunctionManager().getFunctionAt(tgt);
            out.println(String.format("  +0x%02x = 0x%x  %s", i * 8, val, tf != null ? tf.getName() : ""));
        }

        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
