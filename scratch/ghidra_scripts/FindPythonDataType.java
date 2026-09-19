//@category ROS_RE
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.LinkedHashSet;
import java.util.Set;

public class FindPythonDataType extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_pythondatatype.txt";
        PrintWriter out = new PrintWriter(new FileWriter(outPath, false));

        DecompInterface decomp = new DecompInterface();
        decomp.setOptions(new DecompileOptions());
        decomp.openProgram(currentProgram);

        String needle = "PythonDataType::createFromStream";
        Set<Function> funcs = new LinkedHashSet<>();
        DataIterator it = currentProgram.getListing().getDefinedData(true);
        while (it.hasNext()) {
            Data d = it.next();
            if (!d.hasStringValue()) continue;
            Object v = d.getValue();
            if (v == null || !v.toString().contains(needle)) continue;
            out.println("string @ " + d.getAddress() + " : " + v);
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(d.getAddress());
            while (refs.hasNext()) {
                Reference r = refs.next();
                Function f = currentProgram.getFunctionManager().getFunctionContaining(r.getFromAddress());
                out.println("   ref from " + r.getFromAddress() + " in " + (f != null ? f.getName() : "UNKNOWN"));
                if (f != null) funcs.add(f);
            }
        }
        out.println();

        for (Function f : funcs) {
            out.println("=== " + f.getName() + " @ " + f.getEntryPoint() + " ===");
            DecompileResults res = decomp.decompileFunction(f, 300, new ghidra.util.task.ConsoleTaskMonitor());
            if (res != null && res.decompileCompleted()) {
                for (String line : res.getDecompiledFunction().getC().split("\n")) {
                    if (line.trim().startsWith("/* catch()") || line.trim().startsWith("/* try {")) continue;
                    out.println(line);
                }
            }
            out.println();
        }

        decomp.dispose();
        out.flush();
        out.close();
        println("Wrote output to " + outPath);
    }
}
