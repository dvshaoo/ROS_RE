//@category ROS_RE
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.Memory;

import java.io.FileWriter;
import java.io.PrintWriter;

public class DisasmFilterConsts extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_filter_consts.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));

        Listing listing = currentProgram.getListing();
        Memory mem = currentProgram.getMemory();

        // Disassembly of the group-filter loop head in FUN_00acf5ec
        Address start = currentProgram.getAddressFactory().getAddress("00acf5ec");
        out.println("=== disassembly FUN_00acf5ec (first 60 instrs) ===");
        Instruction ins = listing.getInstructionAt(start);
        for (int i = 0; i < 60 && ins != null; i++) {
            out.println(String.format("  %s  %s", ins.getAddress(), ins.toString()));
            ins = ins.getNext();
        }
        out.println();

        // Raw bytes at the two constant tables the decompiler referenced
        String[] consts = {"02b62400", "02b61b60"};
        for (String c : consts) {
            Address a = currentProgram.getAddressFactory().getAddress(c);
            out.println("=== bytes at " + c + " (block " +
                    (mem.getBlock(a) != null ? mem.getBlock(a).getName() : "?") + ") ===");
            byte[] buf = new byte[32];
            try {
                mem.getBytes(a, buf);
                StringBuilder sb = new StringBuilder();
                for (byte b : buf) sb.append(String.format("%02x ", b));
                out.println("  " + sb);
            } catch (Exception e) {
                out.println("  read error: " + e.getMessage());
            }
        }

        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
