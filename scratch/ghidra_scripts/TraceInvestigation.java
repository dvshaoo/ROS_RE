// TraceInvestigation.java
// Ghidra headless post-script: dumps decompiled pseudocode, callers, and callees
// for a list of already-established addresses of interest from the ROS_RE
// static investigation, and searches the symbol table for Account/Avatar/
// Character/Lobby-related names (including demangled RTTI symbols).
//
// Output is written to scratch/ghidra_trace_output.txt (plain text) so it can
// be read directly without needing the Ghidra GUI.
//
//@category ROS_RE

import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.ReferenceManager;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolIterator;
import ghidra.program.model.symbol.SymbolTable;
import ghidra.util.task.ConsoleTaskMonitor;

import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.List;

public class TraceInvestigation extends GhidraScript {

    private PrintWriter out;
    private DecompInterface decomp;

    @Override
    protected void run() throws Exception {
        String outPath = "C:\\Users\\Raysoo\\Downloads\\ROS_RE\\scratch\\ghidra_trace_output.txt";
        out = new PrintWriter(new FileWriter(outPath, false));

        decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        // Addresses of interest already established by this project's own
        // Capstone-based static analysis across many prior E2E passes.
        // Format: {address_hex, human_label}
        String[][] targets = {
            {"94c540", "generic entity-RPC dispatch (checks entity+0x140 before invoking bound method) - E2E-025/029"},
            {"93a5e4", "candidate re-examined for entity+0x140 setter (E2E-036/synthesis)"},
            {"9387cc", "createBaseTypePlayer / calls registerRetryingRequest chain"},
            {"937128", "registerRetryingRequest (retry infra shared with LoginApp logOnBegin)"},
            {"9384a8", "BaseAppLoginRequest::setNubAndSend"},
            {"984a54", "Channel constructor"},
            {"985368", "Channel destructor-worker (reads Channel+0x140 on cleanup) - E2E-036"},
            {"985e84", "Channel::send()-adjacent, reads +0x140 behind debug-flag - E2E-036"},
            {"992994", "indexed-channel map INSERT (E2E-017/018)"},
            {"9929e4", "indexed-channel map REMOVE-adjacent - E2E-030"},
            {"947dc4", "createBasePlayer ClientInterface descriptor"},
            {"918504", "ClientApp::onBasePlayerCreate"},
            {"9818c8", "address-to-string (IP formatting) used in checkScriptBaseAppAddr"},
            {"98a3f4", "string-assign used in checkScriptBaseAppAddr"},
            {"93a134", "checkScriptBaseAppAddr"},
            {"93a404", "finalizeLoginAttempt-equivalent"},
            {"938070", "LoginHandler::handleMessage"},
            {"938234", "onLoginReply decrypt call site"},
            {"989600", "LoginReply-specific Blowfish decrypt (NOT generic, per E2E-016)"},
            {"98924c", "generic EncryptionFilter decrypt entry"},
            {"9395cc", "wrapper leading to E2E-030 setter, RTTI vtable slot"},
        };

        long imageBase = currentProgram.getImageBase().getOffset();
        out.println("=== ROS_RE Ghidra Trace Investigation ===");
        out.println("Program: " + currentProgram.getName());
        out.println("Image base: 0x" + Long.toHexString(imageBase));
        out.println("Language: " + currentProgram.getLanguage().getLanguageID());
        out.println();

        for (String[] t : targets) {
            String addrHex = t[0];
            String label = t[1];
            dumpTarget(addrHex, label, imageBase);
        }

        out.println();
        out.println("=== Symbol table search: Account/Avatar/Character/Lobby/Player/CreatePlayer/Match/onLogin/onEnter ===");
        searchSymbols();

        out.flush();
        out.close();
        decomp.dispose();
        println("Wrote trace output to " + outPath);
    }

    private void dumpTarget(String addrHex, String label, long imageBase) {
        try {
            long staticOffset = Long.parseLong(addrHex, 16);
            // CONFIRMED via QuickCheck.java cross-validation against 4 well-known
            // anchors (0x938070=LoginHandler::onLoginReply with matching log
            // string, 0x94c540=entity+0x140 dispatcher, 0x989600/0x98924c=
            // EncryptionFilter decrypt variants with matching BF_ecb_encrypt/
            // wastage logic): the correct mapping is imageBase + staticOffset,
            // where Ghidra assigned imageBase=0x100000 to this ELF import.
            Address addr = toAddr(imageBase + staticOffset);

            out.println("--------------------------------------------------------------------");
            out.println("TARGET 0x" + addrHex + " (runtime " + addr + ") : " + label);

            Function func = getFunctionAt(addr);
            if (func == null) {
                func = currentProgram.getFunctionManager().getFunctionContaining(addr);
            }
            if (func == null) {
                out.println("  [No function found at or containing this address]");
                return;
            }
            out.println("  Function: " + func.getName() + " @ " + func.getEntryPoint());
            out.println("  Signature: " + func.getSignature());

            // Callers (who calls this function)
            out.println("  --- Callers ---");
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(func.getEntryPoint());
            int callerCount = 0;
            while (refs.hasNext() && callerCount < 30) {
                Reference r = refs.next();
                if (r.getReferenceType().isCall()) {
                    Function callerFunc = currentProgram.getFunctionManager().getFunctionContaining(r.getFromAddress());
                    String callerName = callerFunc != null ? callerFunc.getName() + " @ " + callerFunc.getEntryPoint() : "?";
                    out.println("    from " + r.getFromAddress() + " (" + callerName + ")");
                    callerCount++;
                }
            }
            if (callerCount == 0) {
                out.println("    [No direct call-type references found -- may be reached via virtual dispatch/register-indexed call]");
            }

            // Callees (what this function calls)
            out.println("  --- Callees (direct calls within this function) ---");
            List<String> callees = new ArrayList<>();
            currentProgram.getListing().getInstructions(func.getBody(), true).forEach(instr -> {
                if (instr.getFlowType().isCall()) {
                    Address[] flows = instr.getFlows();
                    for (Address f : flows) {
                        Function calleeFunc = currentProgram.getFunctionManager().getFunctionContaining(f);
                        String name = calleeFunc != null ? calleeFunc.getName() + " @ " + calleeFunc.getEntryPoint() : f.toString();
                        callees.add(name);
                    }
                }
            });
            for (String c : callees) {
                out.println("    calls " + c);
            }

            // Decompile
            out.println("  --- Decompiled pseudocode ---");
            DecompileResults res = decomp.decompileFunction(func, 60, new ConsoleTaskMonitor());
            if (res != null && res.decompileCompleted()) {
                String code = res.getDecompiledFunction().getC();
                out.println(code);
            } else {
                out.println("    [Decompilation failed or timed out: " + (res != null ? res.getErrorMessage() : "null result") + "]");
            }
        } catch (Exception e) {
            out.println("  [ERROR processing target 0x" + addrHex + ": " + e + "]");
        }
    }

    private void searchSymbols() {
        String[] keywords = {
            "account", "avatar", "player", "character", "createcharacter",
            "createplayer", "lobby", "enterlobby", "match", "reqmatch",
            "onlogin", "onenter", "onchannellogin", "createbaseplayer",
            "enableentities", "handshake"
        };
        SymbolTable st = currentProgram.getSymbolTable();
        SymbolIterator allSymbols = st.getAllSymbols(true);
        int found = 0;
        while (allSymbols.hasNext() && found < 500) {
            Symbol sym = allSymbols.next();
            String name = sym.getName();
            String nameLower = name.toLowerCase();
            for (String kw : keywords) {
                if (nameLower.contains(kw)) {
                    out.println("  " + sym.getAddress() + "  " + name + "  [" + sym.getSymbolType() + "]");
                    found++;
                    break;
                }
            }
        }
        out.println("  (" + found + " matching symbols found, capped at 500)");
    }
}
