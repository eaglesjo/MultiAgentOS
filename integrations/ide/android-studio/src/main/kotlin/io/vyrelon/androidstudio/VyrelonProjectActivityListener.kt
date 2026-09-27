package io.vyrelon.androidstudio

import com.intellij.openapi.project.Project
import com.intellij.openapi.project.ProjectManagerListener

class VyrelonProjectActivityListener : ProjectManagerListener {
    override fun projectOpened(project: Project) {
        val adapter = AndroidStudioAdapter()
        adapter.publishContext(adapter.context(project))
    }
}
