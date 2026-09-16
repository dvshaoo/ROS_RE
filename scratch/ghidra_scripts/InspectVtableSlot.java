// InspectVtableSlot.java
// Dumps context around the 3 data/indirection references found pointing at
// FUN_00a4c540 (static 0x94c540): what symbol/data structure owns each slot,
// nearby RTTI typeinfo (Itanium C++ ABI: typeinfo ptr sits right before the
// first vtable function slot, i.e. at vtable_addr - 8 for a class with no
// vcall-offset entries, or check symbol table for "_ZTV"/"_ZTI" mangled
// names near each address), and who references the CONTAINING vtable
// address itself (that tells us which code loads this vtable -> which class
// gets constructed with it).
//@category ROS_RE

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Data;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolTable;
import ghidra.program.model.mem.Memory;

import java.io.FileWriter;
import java.io.PrintWriter;

public class InspectVtableSlot extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_vtable_inspect.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));

        long[] hitOffsets = {0x33175d0L, 0x33f7368L, 0x38d7cb8L};
        SymbolTable st = currentProgram.getSymbolTable();
        Memory mem = currentProgram.getMemory();

        for (long off : hitOffsets) {
            Address a = toAddr(off);
            out.println("=== Slot at " + a + " ===");

            // Symbol directly at this address
            Symbol[] syms = st.getSymbols(a);
            for (Symbol s : syms) {
                out.println("  symbol here: " + s.getName() + " type=" + s.getSymbolType());
            }
            if (syms.length == 0) out.println("  [no symbol directly at this address]");

            // Look backwards up to 64 bytes (8 pointer-slots) for the nearest
            // preceding symbol -- that's likely the vtable base / typeinfo.
            out.println("  --- preceding symbols within 64 bytes ---");
            for (long back = 8; back <= 64; back += 8) {
                Address p = a.subtract(back);
                Symbol[] s2 = st.getSymbols(p);
                for (Symbol s : s2) {
                    out.println("    -" + back + ": " + p + "  " + s.getName() + " [" + s.getSymbolType() + "]");
                }
            }

            // Data value + type at the address itself
            Data d = getDataAt(a);
            if (d != null) {
                out.println("  data type: " + d.getDataType().getName() + " value=" + d.getValue());
            }

            // Who references THIS address (i.e. who loads a pointer to this
            // vtable region -- reveals the constructor/class using it)
            out.println("  --- references TO this slot address ---");
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(a);
            int c = 0;
            while (refs.hasNext() && c < 20) {
                Reference r = refs.next();
                out.println("    from " + r.getFromAddress() + " type=" + r.getReferenceType());
                c++;
            }
            if (c == 0) out.println("    [none]");
            out.println();
        }

        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
