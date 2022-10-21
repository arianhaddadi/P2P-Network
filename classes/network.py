from node import Node
import threading
import random
import shutil
import os



class Network:
    def __init__(self, numOfNodes, N):
        self.numOfNodes = numOfNodes
        self.N = N
        self.nodesPortsInterval = (10000, 11000)
        self.done = False

    def prepareNodesPortsList(self):
        self.nodesPortsList = []
        for i in range(self.numOfNodes):
            nodePort = random.randint(self.nodesPortsInterval[0], self.nodesPortsInterval[1])
            while nodePort in self.nodesPortsList:
                nodePort = random.randint(self.nodesPortsInterval[0], self.nodesPortsInterval[1])
            self.nodesPortsList.append(nodePort)

    def createNodes(self):
        self.prepareNodesPortsList()
        self.nodes = []
        for i in range(len(self.nodesPortsList)):
            self.nodes.append(Node(self.nodesPortsList[i], self.nodesPortsList[:i] + self.nodesPortsList[i+1:], self.N))
 
    def endSimulation(self):
        for i in range(len(self.nodes)):
            self.nodes[i].terminateProcess()
        self.done = True

    def enableNode(self, nodeNum):
        self.nodes[nodeNum].resume()

    def disableNodeRandomly(self):
        nodeNum = random.randint(0, self.numOfNodes - 1)
        self.nodes[nodeNum].stop()
        starter = threading.Timer(20, self.enableNode, [nodeNum])
        starter.daemon = True 
        starter.start()

    def createLogFiles(self):
        shutil.rmtree("logs")
        os.mkdir("logs")
        for node in self.nodes:
            node.writeInLogFile()

    def startSimulation(self):
        self.createNodes()
        for i in range(len(self.nodes)):
            threading.Thread(target=self.nodes[i].start).start()

        threading.Timer(5 * 60, self.endSimulation).start()
        while self.done is False:
            threading.Event().wait(10)
            self.disableNodeRandomly()
        self.createLogFiles()