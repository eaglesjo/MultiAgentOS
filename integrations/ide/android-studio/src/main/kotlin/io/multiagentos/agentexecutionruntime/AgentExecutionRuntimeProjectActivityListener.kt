package io.multiagentos.agentexecutionruntime

import com.intellij.openapi.project.Project
import com.intellij.openapi.project.ProjectManagerListener

class AgentExecutionRuntimeProjectActivityListener : ProjectManagerListener {
    override fun projectOpened(project: Project) {
        val adapter = AndroidStudioAdapter()
        adapter.publishContext(adapter.context(project))
    }
}
