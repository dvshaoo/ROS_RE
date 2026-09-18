//@category ROS_RE
// Ghidra's decompile of FUN_00a8384c (the Bundle-iterator "end" sentinel
// constructor) showed a single-parameter signature, but its caller passes
// 2 arguments (FUN_00a8384c(auStack_170, ptVar24)). Dumping raw
// disassembly to check whether the second argument (x1 register per
// AArch64 calling convention) is genuinely unused, or whether Ghidra's
// decompiler dropped/misattributed it -- this is the key remaining gap in
// GHIDRA_PACKET_PARSER_TRACE.md's exact-fit contradiction.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;

import java.io.FileWriter;
import java.io.PrintWriter;

public class DisasmSentinelCtor extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_sentinelctor_disasm.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));

        Address addr = toAddr(0xa8384cL);
        Function f = getFunctionAt(addr);
        out.println("Function: " + (f != null ? f.getName() + " @ " + f.getEntryPoint() + " body=" + f.getBody() : "NOT FOUND"));
        if (f != null) {
            InstructionIterator it = currentProgram.getListing().getInstructions(f.getBody(), true);
            while (it.hasNext()) {
                Instruction ins = it.next();
                out.println(ins.getAddress() + "  " + ins.toString());
            }
        }

        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
