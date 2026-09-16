// FindVtableCallers.java
// Ghidra headless post-script: finds ALL references (not just call-type) to
// FUN_00a4c540 (the entity+0x140 RPC dispatcher, static offset 0x94c540),
// including data references from vtables/relocation entries, since the
// project's static analysis and the first TraceInvestigation.java pass both
// found zero direct-call xrefs (it's reached via virtual dispatch).
//
// Also dumps any defined data pointing AT this function's address anywhere
// in the program (vtable slots typically show up as DATA refs of type DATA
// or as raw pointer values in .data.rel.ro / .rodata).
//
//@category ROS_RE

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.ReferenceManager;

import java.io.FileWriter;
import java.io.PrintWriter;

public class FindVtableCallers extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_vtable_callers.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));

        long imageBase = currentProgram.getImageBase().getOffset();
        long staticOffset = 0x94c540L;
        Address target = toAddr(imageBase + staticOffset);
        out.println("Target function address: " + target + " (static 0x" + Long.toHexString(staticOffset) + ")");

        Function func = getFunctionAt(target);
        out.println("Function: " + (func != null ? func.getName() : "null"));
        out.println();

        // 1) ALL references (any type) to the function entry point
        out.println("=== ALL references to function entry (any ref type) ===");
        ReferenceManager rm = currentProgram.getReferenceManager();
        ReferenceIterator refs = rm.getReferencesTo(target);
        int count = 0;
        while (refs.hasNext()) {
            Reference r = refs.next();
            out.println("  from " + r.getFromAddress() + "  type=" + r.getReferenceType()
                    + "  opIndex=" + r.getOperandIndex());
            count++;
        }
        out.println("Total: " + count);
        out.println();

        // 2) Scan defined Data items across the whole program for a raw pointer
        //    value equal to target (covers vtable slots Ghidra didn't auto-mark
        //    as references, e.g. inside an undifferentiated data blob).
        out.println("=== Scanning defined Data for raw pointer == target ===");
        long targetOff = target.getOffset();
        Memory mem = currentProgram.getMemory();
        int dataHits = 0;
        DataIterator dataIt = currentProgram.getListing().getDefinedData(true);
        while (dataIt.hasNext()) {
            Data d = dataIt.next();
            if (d.isPointer()) {
                Object val = d.getValue();
                if (val instanceof Address) {
                    if (((Address) val).getOffset() == targetOff) {
                        out.println("  pointer at " + d.getAddress() + " -> " + val);
                        dataHits++;
                    }
                }
            }
        }
        out.println("Total pointer hits: " + dataHits);
        out.println();

        // 3) Raw byte-pattern scan of all initialized memory blocks for the
        //    little-endian 8-byte encoding of target's RAW file-relative
        //    offset (staticOffset), since ELF .rela.dyn relocations for
        //    vtables often store the pre-relocation addend as the plain
        //    static offset rather than the Ghidra-loaded runtime address.
        out.println("=== Raw byte scan for 8-byte LE pattern of static offset 0x"
                + Long.toHexString(staticOffset) + " ===");
        byte[] pattern = new byte[8];
        long v = staticOffset;
        for (int i = 0; i < 8; i++) {
            pattern[i] = (byte) (v & 0xFF);
            v >>= 8;
        }
        int rawHits = 0;
        for (MemoryBlock block : mem.getBlocks()) {
            if (!block.isInitialized()) continue;
            Address found = block.getStart();
            while (true) {
                Address hit = mem.findBytes(found, block.getEnd(), pattern, null, true, monitor);
                if (hit == null) break;
                out.println("  raw offset pattern at " + hit + " (block " + block.getName() + ")");
                rawHits++;
                try {
                    found = hit.add(1);
                } catch (Exception e) {
                    break;
                }
                if (found.compareTo(block.getEnd()) >= 0) break;
            }
        }
        out.println("Total raw-offset pattern hits: " + rawHits);

        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
