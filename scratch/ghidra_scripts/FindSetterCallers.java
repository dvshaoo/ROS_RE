// FindSetterCallers.java
// Same any-reference-type + raw-byte-pattern technique as FindVtableCallers,
// but generalized to a list of static offsets, targeting FUN_00a3a5e4
// (the entity+0x140 SETTER candidate: *(param_1+0x140)=param_2) to find
// its vtable slot / real caller, since this is the actual gate-setter the
// live server needs to trigger -- not just the dispatcher that reads it.
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
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolTable;

import java.io.FileWriter;
import java.io.PrintWriter;

public class FindSetterCallers extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_setter_callers.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));

        long imageBase = currentProgram.getImageBase().getOffset();
        long[] staticOffsets = {0x93a5e4L, 0x473d0L};
        Memory mem = currentProgram.getMemory();
        SymbolTable st = currentProgram.getSymbolTable();
        ReferenceManager rm = currentProgram.getReferenceManager();

        for (long so : staticOffsets) {
            Address target = toAddr(imageBase + so);
            Function func = getFunctionAt(target);
            out.println("=== Target static 0x" + Long.toHexString(so) + " -> " + target
                    + " (" + (func != null ? func.getName() : "no func") + ") ===");

            out.println("--- ALL references (any type) to function entry ---");
            ReferenceIterator refs = rm.getReferencesTo(target);
            int c = 0;
            while (refs.hasNext()) {
                Reference r = refs.next();
                out.println("  from " + r.getFromAddress() + " type=" + r.getReferenceType());
                c++;
            }
            out.println("Total: " + c);

            out.println("--- Defined-data pointer scan for value == target ---");
            long targetOff = target.getOffset();
            int dataHits = 0;
            DataIterator dataIt = currentProgram.getListing().getDefinedData(true);
            while (dataIt.hasNext()) {
                Data d = dataIt.next();
                if (d.isPointer()) {
                    Object val = d.getValue();
                    if (val instanceof Address && ((Address) val).getOffset() == targetOff) {
                        out.println("  pointer at " + d.getAddress() + " -> " + val);
                        // check for a preceding label within 32 bytes (typeinfo/vtable name)
                        for (long back = 8; back <= 32; back += 8) {
                            Address p = d.getAddress().subtract(back);
                            Symbol[] syms = st.getSymbols(p);
                            for (Symbol s : syms) {
                                out.println("      -" + back + ": " + p + " " + s.getName());
                            }
                        }
                        dataHits++;
                    }
                }
            }
            out.println("Total pointer hits: " + dataHits);

            out.println("--- Raw 8-byte LE static-offset pattern scan ---");
            byte[] pattern = new byte[8];
            long v = so;
            for (int i = 0; i < 8; i++) { pattern[i] = (byte) (v & 0xFF); v >>= 8; }
            int rawHits = 0;
            for (MemoryBlock block : mem.getBlocks()) {
                if (!block.isInitialized()) continue;
                Address found = block.getStart();
                while (true) {
                    Address hit = mem.findBytes(found, block.getEnd(), pattern, null, true, monitor);
                    if (hit == null) break;
                    out.println("  raw pattern at " + hit + " (block " + block.getName() + ")");
                    rawHits++;
                    try { found = hit.add(1); } catch (Exception e) { break; }
                    if (found.compareTo(block.getEnd()) >= 0) break;
                }
            }
            out.println("Total raw hits: " + rawHits);
            out.println();
        }

        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
