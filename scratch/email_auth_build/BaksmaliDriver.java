import com.android.tools.smali.baksmali.Baksmali;
import com.android.tools.smali.baksmali.BaksmaliOptions;
import com.android.tools.smali.dexlib2.DexFileFactory;
import com.android.tools.smali.dexlib2.Opcodes;
import com.android.tools.smali.dexlib2.dexbacked.DexBackedDexFile;
import com.android.tools.smali.dexlib2.iface.MultiDexContainer;

import java.io.File;

public class BaksmaliDriver {
    public static void main(String[] args) throws Exception {
        File dexFile = new File(args[0]);
        File outDir = new File(args[1]);
        Opcodes opcodes = new Opcodes(21, -1);
        MultiDexContainer container = DexFileFactory.loadDexContainer(dexFile, opcodes);
        for (Object nameObj : container.getDexEntryNames()) {
            String name = (String) nameObj;
            DexBackedDexFile dex = container.getEntry(name).getDexFile();
            BaksmaliOptions options = new BaksmaliOptions();
            Baksmali.disassembleDexFile(dex, outDir, 1, options);
        }
        System.out.println("Done.");
    }
}
