import socket
import threading
import random
import time
import json
import shutil
import os
import networkx as nx
import matplotlib.pyplot as plt


class Node:
    def __init__(self, port, otherNodes, N):
        self.ip = "127.0.0.1"
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.ip, self.port))
        self.N = N
        self.otherNodes = otherNodes
        self.unidirectionalConnections = []
        self.bidirectionalConnections = []
        self.done = False
        self.disabled = False
        self.message = {
            "id": self.port,
            "src": {
                "IP": "localhost",
                "port": self.port
            },
            "type": "Hello",
            "uniNeighbours": self.unidirectionalConnections,
            "biNeighbours": self.bidirectionalConnections,
            "lastSent": None,
            "lastReceived": None
        }
        self.neighboursInfo = {}
        for node in self.otherNodes:
            self.neighboursInfo[node] = {
                "lastSent": 0,
                "lastReceived": 0,
                "packetsReceived": 0,
                "packetsSent": 0,
                "becameNeighbour": False,
                "connectionLength": 0,
                "connectionStartingTime": None,
                "neighbours": []
            }
        
    def stop(self):
        self.disabled = True
        self.restartNeighboursList()

    def resume(self):
        self.disabled = False
        threading.Thread(target=self.findNewNeighbours).start()

    def restartNeighboursList(self):
        for connection in self.unidirectionalConnections + self.bidirectionalConnections:
            self.otherNodes.append(connection)
        for biConnection in self.bidirectionalConnections:
            info = self.neighboursInfo[biConnection]
            info["connectionLength"] += time.time() - info["connectionStartingTime"]
            info["connectionStartingTime"] = None
        self.unidirectionalConnections.clear()
        self.bidirectionalConnections.clear()

    def terminateProcess(self):
        self.done = True

    def findNewNeighbours(self):
        while len(self.bidirectionalConnections) < self.N:
            if not(self.done or self.disabled):
                nominees = self.unidirectionalConnections + self.otherNodes if len(self.otherNodes) == 0 else self.otherNodes 
                nominee = nominees[random.randint(0, len(nominees) - 1)]
                self.sendMessage([nominee])
            elif self.done:
                break
            threading.Event().wait(2)

    def moveNodeBetweenConnectionLists(self, srcList, dstList, node, deleteNeighbours):
        srcList.remove(node)
        dstList.append(node)
        if deleteNeighbours:
            self.neighboursInfo[node]["neighbours"].clear()

    def checkUniConnections(self):
        for node in self.unidirectionalConnections:
            if time.time() - self.neighboursInfo[node]["lastReceived"] > 8:
                self.moveNodeBetweenConnectionLists(self.unidirectionalConnections, self.otherNodes, node, True)

    def checkBiConnections(self):
        for node in self.bidirectionalConnections:
            if time.time() - self.neighboursInfo[node]["lastReceived"] > 8:
                self.moveNodeBetweenConnectionLists(self.bidirectionalConnections, self.otherNodes, node, True)
                info = self.neighboursInfo[node]
                info["connectionLength"] += time.time() - info["connectionStartingTime"]
                info["connectionStartingTime"] = None
                threading.Thread(target=self.findNewNeighbours).start()

    def checkConnections(self):
        while True:
            threading.Event().wait(8)
            if not(self.done or self.disabled):
                self.checkUniConnections()
                self.checkBiConnections()
            elif self.done:
                break

    def addToBidirectionalConnections(self, data):
        if data["id"] in self.unidirectionalConnections:
            self.unidirectionalConnections.remove(data["id"])
        elif data["id"] in self.otherNodes:
            self.otherNodes.remove(data["id"])
        self.bidirectionalConnections.append(data["id"])
        self.neighboursInfo[data["id"]]["becameNeighbour"] = True
        self.neighboursInfo[data["id"]]["connectionStartingTime"] = time.time()

    def updateBidirectionalConnectionInfo(self, info, data):
        info["neighbours"] = data["biNeighbours"]
        info["packetsReceived"] += 1

    def startReceiving(self):
        checkingConnectionThread = threading.Thread(target=self.checkConnections) 
        checkingConnectionThread.daemon = True
        checkingConnectionThread.start()
        while True:
            if not(self.done or self.disabled):
                data, addr = self.socket.recvfrom(1000)
                if random.randint(1, 100) <= 5:
                    continue
                data = json.loads(data.decode())
                info = self.neighboursInfo[data["id"]]
                info["lastReceived"] = time.time()
                if info["connectionStartingTime"] is not None:
                    if self.port in data["uniNeighbours"] + data["biNeighbours"]:
                        self.updateBidirectionalConnectionInfo(info, data)
                    else:
                        self.moveNodeBetweenConnectionLists(self.bidirectionalConnections, self.unidirectionalConnections, data["id"], False)
                        info["connectionLength"] += time.time() - info["connectionStartingTime"]
                        info["connectionStartingTime"] = None
                        threading.Thread(target=self.findNewNeighbours).start()
                elif len(self.bidirectionalConnections) < self.N:
                    if self.port in data["uniNeighbours"] + data["biNeighbours"]:
                        self.addToBidirectionalConnections(data)
                        self.updateBidirectionalConnectionInfo(info, data)
                    else:
                        if data["id"] not in self.unidirectionalConnections:
                            self.otherNodes.remove(data["id"])
                            self.unidirectionalConnections.append(data["id"])
            elif self.done:
                break

    def prepareMessage(self, destination):
        self.message["lastReceived"] = self.neighboursInfo[destination]["lastReceived"]
        self.message["lastSent"] = self.neighboursInfo[destination]["lastSent"]

    def sendMessage(self, destinationNodes):
        for destination in destinationNodes:
            self.prepareMessage(destination)
            self.socket.sendto(json.dumps(self.message).encode(), (self.ip, destination))
            if destination in self.bidirectionalConnections:
                self.neighboursInfo[destination]["packetsSent"] += 1
                self.neighboursInfo[destination]["lastSent"] = time.time()

    def getAddressForm(self, port):
        return self.ip + ":" + str(port)

    def drawPlot(self, folderAddress):
        graph = nx.DiGraph()

        nodes = [self.getAddressForm(self.port)]
        for neighbour in self.neighboursInfo:
            nodes.append(self.getAddressForm(neighbour))
        graph.add_nodes_from(nodes)

        for neighbour in self.neighboursInfo:
            bi = self.neighboursInfo[neighbour]["neighbours"]
            for biConnection in bi:
                if biConnection != self.port:
                    graph.add_edge(self.getAddressForm(biConnection), self.getAddressForm(neighbour))
                    graph.add_edge(self.getAddressForm(neighbour), self.getAddressForm(biConnection))

        for uniConnection in self.unidirectionalConnections:
                graph.add_edge(self.getAddressForm(self.port), self.getAddressForm(uniConnection))
        for biConnection in self.bidirectionalConnections:
            graph.add_edge(self.getAddressForm(biConnection), self.getAddressForm(self.port))
            graph.add_edge(self.getAddressForm(self.port), self.getAddressForm(biConnection))

        pos = nx.circular_layout(graph)
        plt.figure(figsize=(10, 10))
        plt.margins(0.15)
        nodeColors = ["blue"] + ["orange"] * 5
        nx.draw(graph, pos, with_labels=True, node_color=nodeColors, node_size=9000)
        plt.savefig(folderAddress + "/port_" + str(self.port) + "_topology")
        plt.show()

    def logNeighbourshipHistory(self, fileContent):
        for neighbour in self.neighboursInfo:
            info = self.neighboursInfo[neighbour]
            if info["becameNeighbour"] is True:
                fileContent["Neighbours That Got Connected"].append({
                    "IP": self.ip,
                    "Port": neighbour,
                    "Number of Received Packets": info["packetsReceived"],
                    "Number of Sent Packets": info["packetsSent"]
                })
    
    def logNodesAvailability(self, fileContent):
        for neighbour in self.neighboursInfo:
            info = self.neighboursInfo[neighbour]
            if info["becameNeighbour"] is True:
                fileContent["Other Nodes Availability"][neighbour] = round(info["connectionLength"] / (5 * 60), 2)

    def logCurrentNeighbours(self, fileContent):
        for neighbour in self.bidirectionalConnections:
            fileContent["Current Neighbours"].append(neighbour)

    def logTopology(self, fileContent):
        for neighbour in self.neighboursInfo:
            fileContent["Topology"]["Vertexes"].append(neighbour)
            biConnections = self.neighboursInfo[neighbour]["neighbours"]
            for biConnection in biConnections:
                if biConnection != self.port:
                    fileContent["Topology"]["Edges"].append({
                        "From":self.getAddressForm(neighbour),
                        "To":self.getAddressForm(biConnection)
                    })
                    fileContent["Topology"]["Edges"].append({
                        "From":self.getAddressForm(biConnection),
                        "To":self.getAddressForm(neighbour)
                    })

        for uniConnection in self.unidirectionalConnections:
            fileContent["Topology"]["Edges"].append({
                "From":self.getAddressForm(self.port),
                "To":self.getAddressForm(uniConnection)
            })

        for biConnection in self.bidirectionalConnections:
            fileContent["Topology"]["Edges"].append({
                "From":self.getAddressForm(self.port),
                "To":self.getAddressForm(biConnection)
            })
            fileContent["Topology"]["Edges"].append({
                "From":self.getAddressForm(biConnection),
                "To":self.getAddressForm(self.port)
            })

    def writeInLogFile(self):
        with open(str(self.port), "w") as file:
            fileContent = {
                "Neighbours That Got Connected": [],
                "Current Neighbours": [],
                "Other Nodes Availability": {},
                "Topology": {
                    "Vertexes":[],
                    "Edges": []
                }
            }
            self.logNeighbourshipHistory(fileContent)
            self.logNodesAvailability(fileContent)
            self.logCurrentNeighbours(fileContent)
            self.logTopology(fileContent)
            file.write(json.dumps(fileContent, indent=4))
        folderAddress = "logs/port_" + str(self.port)
        os.mkdir(folderAddress)
        shutil.move(str(self.port), folderAddress + "/port_" + str(self.port) + "_logs.json")
        self.drawPlot(folderAddress)       

    def start(self):
        receiveThread = threading.Thread(target=self.startReceiving) 
        receiveThread.daemon = True
        receiveThread.start()
        self.sendMessage(self.otherNodes)
        threading.Thread(target=self.findNewNeighbours).start()
        while True:
            threading.Event().wait(2)
            if not(self.done or self.disabled):
                self.sendMessage(self.bidirectionalConnections if len(self.bidirectionalConnections) >= self.N else self.bidirectionalConnections + self.unidirectionalConnections)
            elif self.done:
                break