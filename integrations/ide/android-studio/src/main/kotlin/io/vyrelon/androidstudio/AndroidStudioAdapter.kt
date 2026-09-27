package io.vyrelon.androidstudio

import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.VirtualFile
import java.net.HttpURLConnection
import java.net.URI

data class IdeContext(
    val projectRoot: String,
    val filePath: String?,
    val languageId: String?,
    val workspaceId: String?,
)

class AndroidStudioAdapter(
    private val endpoint: String = System.getenv("VYRELON_IDE_ENDPOINT") ?: "http://127.0.0.1:8787",
    private val token: String? = System.getenv("VYRELON_IDE_TOKEN")?.takeIf { it.isNotBlank() },
) {
    fun context(project: Project, file: VirtualFile? = null): IdeContext =
        IdeContext(
            projectRoot = project.basePath.orEmpty(),
            filePath = file?.path,
            languageId = file?.extension,
            workspaceId = project.name,
        )

    fun publishContext(context: IdeContext): String =
        postJson("/v1/ide/event", buildJson(context))

    private fun buildJson(context: IdeContext): String {
        val root = escape(context.projectRoot)
        val file = context.filePath?.let { value -> """ + escape(value) + """ } ?: "null"
        val language = context.languageId?.let { value -> """ + escape(value) + """ } ?: "null"
        val workspace = context.workspaceId?.let { value -> """ + escape(value) + """ } ?: "null"
        return """{"kind":"context_changed","context":{"kind":"android_studio","project_root":"$root","file_path":$file,"language_id":$language,"workspace_id":$workspace},"payload":{}}"""
    }

    private fun escape(value: String): String =
        value.replace("\", "\\").replace(""", "\"").replace("
", "\n")

    private fun postJson(path: String, body: String): String {
        val connection = URI.create(endpoint.trimEnd('/') + path).toURL().openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.connectTimeout = 3000
        connection.readTimeout = 10000
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json")
        token?.let { value -> connection.setRequestProperty("Authorization", "Bearer " + value) }
        connection.outputStream.use { output -> output.write(body.toByteArray(Charsets.UTF_8)) }
        return connection.inputStream.bufferedReader().use { reader -> reader.readText() }
    }
}
