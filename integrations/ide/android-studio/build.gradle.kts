plugins {
    kotlin("jvm") version "2.1.20"
    id("org.jetbrains.intellij.platform") version "2.5.0"
}
group = "io.multiagentos.agentexecutionruntime"
version = "0.1.0"
repositories {
    mavenCentral()
    intellijPlatform { defaultRepositories() }
}
dependencies {
    intellijPlatform {
        androidStudio("2024.3.1.15")
        bundledPlugin("com.android.tools.idea")
    }
}
intellijPlatform {
    pluginConfiguration {
        ideaVersion { sinceBuild = "243" }
    }
}
