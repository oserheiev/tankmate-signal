import com.jpexs.decompiler.flash.SWF;
import com.jpexs.decompiler.flash.SWFCompression;
import com.jpexs.decompiler.flash.configuration.Configuration;
import com.jpexs.decompiler.flash.importers.As3ScriptReplacerFactory;
import com.jpexs.decompiler.flash.tags.SymbolClassTag;
import com.jpexs.decompiler.flash.tags.Tag;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

/** Developer-only compiler; the game loads the resulting SWF without Java. */
public class CompileSettingsUi {
    public static void main(String[] args) throws Exception {
        if (args.length != 5 && args.length != 7) {
            throw new IllegalArgumentException("Expected original SWF, lobby SWF, AS source, playerglobal SWC, output");
        }
        Configuration.playerLibLocation.set(args[3]);
        var movie = new SWF(Files.newInputStream(Path.of(args[0])), false);
        var lobby = new SWF(Files.newInputStream(Path.of(args[1])), false);
        var dependencies = List.of(lobby);
        movie.setAbcIndexDependencies(dependencies);
        var rootName = args.length == 7 ? args[5] : "SettingsWindowUI";
        var root = movie.getAS3Packs().stream()
                .filter(pack -> pack.getClassPath().toString().equals(rootName))
                .findFirst().orElseThrow();
        var compiler = As3ScriptReplacerFactory.createFFDec();
        compiler.initReplacement(root, dependencies);
        try {
            compiler.replaceScript(root, Files.readString(Path.of(args[2])), dependencies);
        } finally {
            compiler.deinitReplacement(root);
        }
        if (args.length == 7) {
            for (var tag : movie.getAbcList()) {
                var constants = tag.getABC().constants;
                for (int i = 1; i < constants.getStringCount(); i++) {
                    if (rootName.equals(constants.getString(i))) {
                        constants.setString(i, args[6]);
                    }
                }
                ((Tag) tag).setModified(true);
            }
            for (var tag : movie.getTags()) {
                if (tag instanceof SymbolClassTag symbols) {
                    for (int i = 0; i < symbols.names.size(); i++) {
                        if (rootName.equals(symbols.names.get(i))) {
                            symbols.names.set(i, args[6]);
                            symbols.setModified(true);
                        }
                    }
                }
            }
        }
        movie.compression = SWFCompression.ZLIB;
        try (var output = Files.newOutputStream(Path.of(args[4]))) {
            movie.saveTo(output);
        }
    }
}
