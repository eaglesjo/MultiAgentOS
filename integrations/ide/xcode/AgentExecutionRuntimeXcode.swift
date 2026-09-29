import Foundation
import XcodeKit

final class SourceEditorCommand: NSObject, XCSourceEditorCommand {
    private let bridge = AgentExecutionRuntimeBridge()

    func perform(with invocation: XCSourceEditorCommandInvocation,
                 completionHandler: @escaping (Error?) -> Void) {
        let buffer = invocation.buffer
        let context = IDEContext(
            projectRoot: "",
            filePath: nil,
            languageId: buffer.contentUTI,
            workspaceId: nil
        )
        let event = IDEEvent(
            kind: "context_changed",
            context: context,
            payload: ["complete_buffer": buffer.completeBuffer]
        )
        bridge.publish(event, completion: completionHandler)
    }
}

struct IDEContext: Encodable {
    let projectRoot: String
    let filePath: String?
    let languageId: String?
    let workspaceId: String?
}

struct IDEEvent: Encodable {
    let kind: String
    let context: IDEContext
    let payload: [String: String]
}

final class AgentExecutionRuntimeBridge {
    private let endpoint: URL
    private let token: String?

    init(endpoint: String? = nil, token: String? = nil) {
        let configuredEndpoint = endpoint ?? ProcessInfo.processInfo.environment["AGENT_EXECUTION_RUNTIME_IDE_ENDPOINT"] ?? "http://127.0.0.1:8787"
        let configuredToken = token ?? ProcessInfo.processInfo.environment["AGENT_EXECUTION_RUNTIME_IDE_TOKEN"]
        let base = configuredEndpoint.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        self.endpoint = URL(string: base + "/v1/ide/event")!
        self.token = configuredToken
    }

    func publish(_ event: IDEEvent, completion: @escaping (Error?) -> Void) {
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.timeoutInterval = 10
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        do {
            request.httpBody = try JSONEncoder().encode(event)
        } catch {
            completion(error)
            return
        }
        URLSession.shared.dataTask(with: request) { _, error, _ in
            completion(error)
        }.resume()
    }
}
