import Foundation
import XcodeKit

final class SourceEditorCommand: NSObject, XCSourceEditorCommand {
    private let bridge = VyrelonBridge()

    func perform(with invocation: XCSourceEditorCommandInvocation,
                 completionHandler: @escaping (Error?) -> Void) {
        let context = IDEContext(
            projectRoot: invocation.buffer.contentUTI ?? "",
            filePath: invocation.buffer.completeBuffer,
            languageId: invocation.buffer.contentUTI,
            workspaceId: nil
        )

        do {
            try bridge.publishContext(context)
            completionHandler(nil)
        } catch {
            completionHandler(error)
        }
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

final class VyrelonBridge {
    private let endpoint: URL
    private let token: String?

    init(endpoint: String = "http://127.0.0.1:8787", token: String? = nil) {
        self.endpoint = URL(string: endpoint.trimmingCharacters(in: CharacterSet(charactersIn: "/")) + "/v1/ide/event")!
        self.token = token
    }

    func publishContext(_ context: IDEContext) throws {
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.timeoutInterval = 10
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let event = IDEEvent(
            kind: "context_changed",
            context: context,
            payload: [:]
        )
        request.httpBody = try JSONEncoder().encode(event)

        let semaphore = DispatchSemaphore(value: 0)
        var capturedError: Error?

        URLSession.shared.dataTask(with: request) { _, responseError, _ in
            capturedError = responseError
            semaphore.signal()
        }.resume()

        semaphore.wait()
        if let capturedError {
            throw capturedError
        }
    }
}
