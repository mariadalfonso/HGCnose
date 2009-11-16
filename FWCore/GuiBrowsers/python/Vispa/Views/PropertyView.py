import logging
import sys

from PyQt4.QtCore import Qt,SIGNAL,QCoreApplication,QSize
from PyQt4.QtGui import QTableWidget,QTableWidgetItem,QCheckBox,QWidget,QSpinBox,QHBoxLayout,QVBoxLayout,QLineEdit,QSizePolicy,QTextEdit,QTextOption,QFrame,QToolButton,QPalette,QComboBox, QFileDialog,QTextCursor,QInputDialog,QPushButton,QDialog,QGridLayout,QIcon,QHeaderView

from Vispa.Main.Application import Application
from Vispa.Main.AbstractTab import AbstractTab
from Vispa.Share.BasicDataAccessor import BasicDataAccessor
from Vispa.Views.AbstractView import AbstractView
from Vispa.Share.ThreadChain import ThreadChain

class ClosableProperty(QWidget):
    def __init__(self,property):
        QWidget.__init__(self)
        self.setContentsMargins(0, 0, 0, 0)
        self.setLayout(QHBoxLayout())
        self.layout().setSpacing(0)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(property)
        self._closeButton=QToolButton()
        self._closeButton.setText("x")
        self._closeButton.hide()
        self._property=property
        self.layout().addWidget(self._closeButton)
    def closableProperty(self):
        return self._property
    def closeButton(self):
        return self._closeButton
    def enterEvent(self,event):
        self._closeButton.show()
    def leaveEvent(self,event):
        self._closeButton.hide()

class ComboBoxReturn(QComboBox):
    def keyPressEvent(self,event):
        QComboBox.keyPressEvent(self,event)
        if event.key()==Qt.Key_Return:
            self.emit(SIGNAL("returnPressed()"))

class PropertyView(QTableWidget, AbstractView):
    """ Shows properties of an object in a QTableWidget using the DataAccessor.
    
    The view can be used readonly ('setReadOnly') or for editing.
    On editing the signals 'valueChanged', 'propertyDeleted', 'propertyAdded' are emitted.
    """

    LABEL = "&Property View"
    
    def __init__(self, parent=None, name=None):
        """ Constructor """
        #logging.debug(self.__class__.__name__ + ": __init__()")
        AbstractView.__init__(self)
        QTableWidget.__init__(self, parent)
       
        self._operationId = 0
        self._updatingFlag=0
        self.updateIni = False
        self.setSortingEnabled(False)
        self.verticalHeader().hide()
        self.setSelectionMode(QTableWidget.NoSelection)
        self.clear()        # sets header

        self._readOnly = False
        self._showAddDeleteButtonFlag = False
        
        self.connect(self.horizontalHeader(), SIGNAL("sectionResized(int,int,int)"), self.sectionResized)
        self.connect(self, SIGNAL("itemDoubleClicked(QTableWidgetItem *)"), self.itemDoubleClickedSlot)
        
    def cancel(self):
        """ Stop all running operations.
        """
        self._operationId += 1
        
    def clear(self):
        """ Clear the table and set the header label.
        """
        QTableWidget.clear(self)
        self.setRowCount(0)
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(['Property', 'Value'])
    
    def propertyWidgets(self):
        """ Return all property widgets in the right column.
        
        Closable as well as normal properties are returned.
        """
        widgets=[]
        for i in range(self.rowCount()):
            widget=self.cellWidget(i,1)
            if isinstance(widget,Property):
                widgets+=[(widget,i)]
            elif hasattr(widget,"closableProperty"):
                widgets+=[(widget.closableProperty(),i)]
        return widgets
        
    def updatePropertyHeight(self,property):
        """ Update the height of the column that holds a certain property.
        """
        #logging.debug(self.__class__.__name__ + ": updatePropertyHeight()")
        for widget,i in self.propertyWidgets():
            if widget==property:
                self.verticalHeader().resizeSection(i, property.properyHeight())
                return
    
    def append(self, property):
        """ Adds a property to the PropertyView and returns it.
        """
        property.setPropertyView(self)
        if self._readOnly:
            property.setReadOnly(True)
        self.insertRow(self.lastRow()+1)
        self.setItem(self.lastRow(), 0, LabelItem(property))
        if not self._readOnly and self._showAddDeleteButtonFlag and property.deletable():
            widget=ClosableProperty(property)
            self.connect(widget.closeButton(), SIGNAL('clicked(bool)'), self.removeProperty)
            self.setCellWidget(self.lastRow(), 1, widget)
        else:
            self.setCellWidget(self.lastRow(), 1, property)
        self.updatePropertyHeight(property)
        self.connect(property, SIGNAL('updatePropertyHeight'), self.updatePropertyHeight)
        return property

    def lastRow(self):
        """ Return the last row holding a property.
        
        The row with the add new property field is not counted.
        """
        if not self._readOnly and self._showAddDeleteButtonFlag and not self._updatingFlag>0:
            return self.rowCount() - 2
        else:
            return self.rowCount() - 1
    
    def addCategory(self, name):
        """ Add a category row to the tabel which consists of two gray LabelItems.
        """
        self.insertRow(self.lastRow()+1)
        self.setItem(self.lastRow(), 0, LabelItem(name, Qt.lightGray))
        self.setItem(self.lastRow(), 1, LabelItem("", Qt.lightGray))
        self.verticalHeader().resizeSection(self.rowCount() - 1, Property.DEFAULT_HEIGHT)

    def setReadOnly(self, readOnly):
        """ Sets all properties in the PropertyView to read-only.
        
        After calling this function all properties that are added are set to read-only as well.
        """
        #logging.debug('PropertyView: setReadOnly()')
        self._readOnly = readOnly
        for property,i in self.propertyWidgets():
            if property:
                property.setReadOnly(self._readOnly)
    
    def readOnly(self):
        return self._readOnly

    def setShowAddDeleteButton(self,show):
        self._showAddDeleteButtonFlag=show
    
    def showAddDeleteButton(self):
        return self._showAddDeleteButtonFlag
    
    def resizeEvent(self, event):
        """ Resize columns when table size is changed.
        """
        if event != None:
            QTableWidget.resizeEvent(self, event)
        space = self.width() - 4
        if self.verticalScrollBar().isVisible():
            space -= self.verticalScrollBar().width()
        space -= self.columnWidth(0)
        self.setColumnWidth(1, space)
        if self.updateIni:
            self.writeIni()

    def sectionResized(self,index,old,new):
        space = self.width() - 4
        if self.verticalScrollBar().isVisible():
            space -= self.verticalScrollBar().width()
        space -= self.columnWidth(0)
        self.setColumnWidth(1, space)
        if self.updateIni:
            self.writeIni()

    def setDataAccessor(self, accessor):
        """ Sets the DataAccessor from which the object properties are read.
        
        You need to call updateContent() in order to make the changes visible.
        """
        if not isinstance(accessor, BasicDataAccessor):
            raise TypeError(__name__ + " requires data accessor of type BasicDataAccessor.")
        AbstractView.setDataAccessor(self, accessor)

    def appendAddRow(self):
        """ Append a row with a field to add new properties.
        """
        self.insertRow(self.lastRow()+1)
        lineedit=QLineEdit()
        lineedit.setFrame(False)
        lineedit.setContentsMargins(0, 0, 0, 0)
        self.setCellWidget(self.lastRow(), 0, lineedit)
        widget=QWidget()
        widget.setContentsMargins(0, 0, 0, 0)
        widget.setLayout(QHBoxLayout())
        widget.layout().setSpacing(0)
        widget.layout().setContentsMargins(0, 0, 0, 0)
        typelist=ComboBoxReturn()
        types=["String","Boolean","Integer","Double","File","FileVector"]
        for type in types:
            typelist.addItem(type)
        widget.layout().addWidget(typelist)
        addButton=QToolButton()
        addButton.setText("+")
        widget.layout().addWidget(addButton)
        self.setCellWidget(self.lastRow(), 1, widget)
        self.verticalHeader().resizeSection(self.lastRow(), Property.DEFAULT_HEIGHT)
        self.connect(addButton, SIGNAL('clicked(bool)'), self.addProperty)
        self.connect(lineedit, SIGNAL('returnPressed()'), self.addProperty)
        self.connect(typelist, SIGNAL('returnPressed()'), self.addProperty)
        addButton._lineedit=lineedit
        addButton._typelist=typelist
        lineedit._lineedit=lineedit
        lineedit._typelist=typelist
        typelist._lineedit=lineedit
        typelist._typelist=typelist
    
    def updateContent(self):
        """ Fill the properties of an object in the PropertyView using the DataAccessor.
        """
        #logging.debug('PropertyView: updateContent()')
        self.cancel()
        if self.dataAccessor() == None:
            return False
        self._updatingFlag+=1
        self.clear()
        if self.dataObject()==None:
            self._updatingFlag-=1
            return True
        self._ignoreValueChangeFlag = True  # prevent infinite loop
        operationId = self._operationId
        thread = ThreadChain(self.dataAccessor().properties, self.dataObject())
        while thread.isRunning():
            if not Application.NO_PROCESS_EVENTS:
                QCoreApplication.instance().processEvents()
        if operationId != self._operationId:
            self._updatingFlag-=1
            return False
        for property in thread.returnValue():
            if property[0] == "Category":
                self.addCategory(property[1])
            else:
                propertyWidget=PropertyView.propertyWidgetFromProperty(property)
                if propertyWidget:
                    self.append(propertyWidget)
                if isinstance(propertyWidget,QCheckBox):
                    propertyWidget.setChecked(property[2],False)      # strange, QCheckBox forgets its state on append in Qt 4.4.4
        if not self._readOnly and self._showAddDeleteButtonFlag:
            self.appendAddRow()
        self.resizeEvent(None)
        self._ignoreValueChangeFlag = False
        self._updatingFlag-=1
        return self._operationId==operationId

    #@staticmethod
    def propertyWidgetFromProperty(property):
        """ Create a property widget from a property tuple.
        
        This function is static in order to be used by other view, e.g. TableView.
        """
        propertyWidget=None
        if property[0] == "String":
            propertyWidget=StringProperty(property[1], property[2])
        elif property[0] == "MultilineString":
            propertyWidget=StringProperty(property[1], property[2], True)
        elif property[0] == "File":
            propertyWidget=FileProperty(property[1], property[2])
        elif property[0] == "FileVector":
            propertyWidget=FileVectorProperty(property[1], property[2])
        elif property[0] == "Boolean":
            propertyWidget = BooleanProperty(property[1], property[2])
        elif property[0] == "Integer":
            propertyWidget=IntegerProperty(property[1], property[2])
        elif property[0] == "Double":
            propertyWidget=DoubleProperty(property[1], property[2])
        else:
            logging.error(__name__+": propertyWidgetFromProperty() - Unknown property type "+str(property[0]))
            return None
        if len(property) > 3 and property[3]:
            propertyWidget.setUserInfo(property[3])
        if len(property) > 4 and property[4]:
            propertyWidget.setReadOnly(True)
        if len(property) > 5 and property[5]:
            propertyWidget.setDeletable(True)
        return propertyWidget
    propertyWidgetFromProperty = staticmethod(propertyWidgetFromProperty)

    def valueChanged(self, property):
        """ This function is called when a property a changed.
        
        The DataAcessor is called to handle the property change.
        """
        if self.dataAccessor() and not self._ignoreValueChangeFlag:
            if property.value() != self.dataAccessor().propertyValue(self.dataObject(), property.name()):
                if property.value()!=None and self.dataAccessor().setProperty(self.dataObject(), property.name(), property.value()):
                    property.setHighlighted(False)
                    self.emit(SIGNAL('valueChanged'),property.name())
                else:
                    property.setHighlighted(True)

    def removeProperty(self, bool=False):
        """ This function deletes a property.
        
        The DataAcessor is called to handle the property remove.
        """
        property=self.sender().parent()._property
        name=property.name()
        if self.dataAccessor():
            if self.dataAccessor().removeProperty(self.dataObject(), property.name()):
                for p,i in self.propertyWidgets():
                    if p==property:
                        self.removeRow(i)
                self.emit(SIGNAL('propertyDeleted'),name)
        
    def addProperty(self, bool=False):
        """ This function adds a property.
        
        The DataAcessor is called to add the property.
        """
        type=str(self.sender()._typelist.currentText())
        name=str(self.sender()._lineedit.text())
        if type in ["String","File"]:
            value=""
        elif type in ["Integer","Double"]:
            value=0
        elif type in ["FileVector"]:
            value=()
        elif type in ["Boolean"]:
            value=False
        if name==None or name=="":
            QCoreApplication.instance().infoMessage("Please specify name of property.")
            return
        if self.dataAccessor():
            if self.dataAccessor().addProperty(self.dataObject(), name, value):
                property=PropertyView.propertyWidgetFromProperty((type,name,value,None,False,True))
                if property:
                    self.append(property)
                self.sender()._lineedit.setText("")
                property.setFocus()
                self.emit(SIGNAL('propertyAdded'),property.name())
        
    def itemDoubleClickedSlot(self, item):
        """ Slot for itemClicked() signal.
        
        Calls items's property's doubleClicked().
        """
        #logging.debug(self.__class__.__name__ + ": itemDoubleClickedSlot()")
        if item.property():
            item.property().labelDoubleClicked()


class LabelItem(QTableWidgetItem):
    """ A QTableWidgetItem with a convenient constructor. 
    """
    def __init__(self, argument, color=Qt.white):
        """ Constructor.
        
        Argument may be either a string or a Property object.
        If argument is the latter the property's user info will be used for the label's tooltip.
        """
        if isinstance(argument, Property):
            tooltip = argument.name() + " (" + argument.userInfo() + ")"
            name = argument.name()
            self._property = argument
        else:
            tooltip = argument
            name = argument
            self._property = None
            
        QTableWidgetItem.__init__(self, name)
        self.setToolTip(tooltip)
        self.setFlags(Qt.ItemIsEnabled)
        self.setBackgroundColor(color)
    
    def property(self):
        return self._property

class Property(object):
    """ Mother of all properties which can be added to the PropertyView using its append() function.
    """
    
    USER_INFO = "General property"
    DEFAULT_HEIGHT = 20
    
    def __init__(self, name):
        self.setName(name)
        self.setUserInfo(self.USER_INFO)
        self._propertyView = None
        self._deletable=False
        
    def setName(self, name):
        """ Sets the name of this property.
        """
        self._name = name
    
    def name(self):
        """ Return the name of this property.
        """
        return self._name
    
    def setDeletable(self,deletable):
        self._deletable=deletable
    
    def deletable(self):
        return self._deletable
    
    def setPropertyView(self, propertyView):
        """ Sets PropertyView object.
        """
        self._propertyView = propertyView
        
    def propertyView(self):
        """ Returns property view.
        """
        return self._propertyView
    
    def setUserInfo(self, info):
        """ Returns user info string containing information on type of property and what data may be insert.
        """
        self._userInfo=info
    
    def userInfo(self):
        """ Returns user info string containing information on type of property and what data may be insert.
        """
        return self._userInfo
    
    def setReadOnly(self, readOnly):
        """ Disables editing functionality.
        """
        pass
    
    def properyHeight(self):
        """ Return the height of the property widget.
        """
        return self.DEFAULT_HEIGHT
    
    def setValue(self, value):
        """ Abstract function returning current value of this property.
        
        Has to be implemented by properties which allow the user to change their value.
        """
        raise NotImplementedError
    
    def value(self):
        """ Abstract function returning current value of this property.
        
        Has to be implemented by properties which allow the user to change their value.
        """
        raise NotImplementedError
    
    def valueChanged(self):
        """ Slot for change events. 
        
        The actual object which have changed should connect their value changed signal 
        (or similar) to this function to forward change to data accessor of PropertyView.
        """
        logging.debug('Property: valueChanged() ' + str(self.name()))
        if self.propertyView():
            self.propertyView().valueChanged(self)

    def labelDoubleClicked(self):
        """ Called by PropertyView itemDoubleClicked().
        """
        pass
    
    def setHighlighted(self,highlight):
        """ Highlight the property, e.g. change color.
        """
        pass

class BooleanProperty(Property, QCheckBox):
    """ Property holding a check box for boolean values.
    """
    
    USER_INFO = "Enable / Disable"
    
    def __init__(self, name, value):
        """ Constructor.
        """
        Property.__init__(self, name)
        QCheckBox.__init__(self)
        self.connect(self, SIGNAL('stateChanged(int)'), self.valueChanged)
    
    def setChecked(self, check, report=True):
        if not report:
            self.disconnect(self, SIGNAL('stateChanged(int)'), self.valueChanged)
        QCheckBox.setChecked(self, check)
        if not report:
            self.connect(self, SIGNAL('stateChanged(int)'), self.valueChanged)

    def setReadOnly(self, readOnly):
        """ Disables editing functionality.
        """
        if readOnly:
            self.setEnabled(False)
            self.disconnect(self, SIGNAL('stateChanged(int)'), self.valueChanged)
        else:
            self.setEnabled(True)
            self.connect(self, SIGNAL('stateChanged(int)'), self.valueChanged)
        
    def value(self):
        """ Returns True if check box is checked.
        """
        return self.isChecked()

class TextEdit(QTextEdit):
    def focusOutEvent(self,event):
        QTextEdit.focusOutEvent(self,event)
        self.emit(SIGNAL("editingFinished()"))
        
class TextEditWithButtonProperty(Property, QWidget):
    """ This class provides a PropertyView property holding an editable text and a button.
    
    It is possible to hide the button unless the mouse cursor is over the property. This feature is turned on by default. See setAutohideButton().
    If the button is pressed nothing happens. This functionality should be implemented in sub-classes. See buttonClicked().
    The text field can hold single or multiple lines. See setMultiline()
    """
    
    BUTTON_LABEL = ''
    AUTOHIDE_BUTTON = True
    
    def __init__(self, name, value, multiline=False):
        """ The constructor creates a QHBoxLayout and calls createLineEdit(), createTextEdit() and createButton(). 
        """
        Property.__init__(self, name)
        QWidget.__init__(self)
        self._lineEdit = None
        self._textEdit = None
        self._button = None
        self.setAutohideButton(self.AUTOHIDE_BUTTON)
        
        self.setLayout(QHBoxLayout())
        self.layout().setSpacing(0)
        self.layout().setContentsMargins(0, 0, 0, 0)
        
        self._readOnly = False
        self._multiline = False

        self.createLineEdit()
        self.createTextEdit()
        self.createButton()
        self.setMultiline(multiline)
        self.setValue(value)
                
    def setValue(self, value):
        """ Sets value of text edit.
        """
        self._originalValue=value
        if value != None:
            strValue = str(value)
        else:
            strValue = ""
        if not self._readOnly:
            self.disconnect(self._lineEdit, SIGNAL('editingFinished()'), self.valueChanged)
            self.disconnect(self._textEdit, SIGNAL('editingFinished()'), self.valueChanged)
        self._lineEdit.setText(strValue)
        self._lineEdit.setToolTip(strValue)
        self._textEdit.setText(strValue)
        self._textEdit.setToolTip(strValue)
        if not self._readOnly:
            self.connect(self._lineEdit, SIGNAL('editingFinished()'), self.valueChanged)
            self.connect(self._textEdit, SIGNAL('editingFinished()'), self.valueChanged)
        # TODO: sometimes when changing value the text edit appears to be empty when new text is shorter than old text
        #if not self._multiline:
        #    self._textEdit.setCursorPosition(self._textEdit.displayText().length())
                
    def setMultiline(self,multi):
        """ Switch between single and multi line mode.
        """
        self.setValue(self.strValue())
        self._multiline=multi
        if self._multiline:
            self._textEdit.show()
            self._lineEdit.hide()
            self.setFocusProxy(self._textEdit)
        else:
            self._lineEdit.show()
            self._textEdit.hide()
            self.setFocusProxy(self._lineEdit)
        
    def createLineEdit(self, value=None):
        """ This function creates the signle line text field and adds it to the property's layout. 
        """
        self._lineEdit = QLineEdit(self)
        self._lineEdit.setFrame(False)
        self.connect(self._lineEdit, SIGNAL('editingFinished()'), self.valueChanged)
        self._lineEdit.setContentsMargins(0, 0, 0, 0)
        self._lineEdit.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding))
        self.layout().addWidget(self._lineEdit)
        
    def createTextEdit(self, value=None):
        """ This function creates the multi line text field and adds it to the property's layout. 
        """
        self._textEdit = TextEdit(self)
        self._textEdit.setWordWrapMode(QTextOption.NoWrap)
        self._textEdit.setFrameStyle(QFrame.NoFrame)
        self.connect(self._textEdit, SIGNAL('editingFinished()'), self.valueChanged)
        self._textEdit.setContentsMargins(0, 0, 0, 0)
        self._textEdit.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding))
        self.layout().addWidget(self._textEdit)
        
    def properyHeight(self):
        """ Return the estimated height of the property.
        
        The returned height covers the whole text, even if multiline.
        """
        if self._multiline:
            self._textEdit.document().adjustSize()
            height=self._textEdit.document().size().height()+3
            if self._textEdit.horizontalScrollBar().isVisible():
                height+=self._textEdit.horizontalScrollBar().height()+3
            return height
        else:
            return self.DEFAULT_HEIGHT
            
    def lineEdit(self):
        """ Returns line edit.
        """
        return self._lineEdit
        
    def textEdit(self):
        """ Returns text edit.
        """
        return self._textEdit
        
    def createButton(self):
        """ Creates a button and adds it to the property's layout.
        """
        self._button = QToolButton(self)
        self._button.setText(self.BUTTON_LABEL)
        self._button.setContentsMargins(0, 0, 0, 0)
        self.connect(self._button, SIGNAL('clicked(bool)'), self.buttonClicked)
        self.layout().addWidget(self._button)
        
        if self.autohideButtonFlag:
            self._button.hide()
    
    def button(self):
        """ Return button.
        """
        return self._button
    
    def hasButton(self):
        """ Returns True if the button has been created, otherwise False is returned. 
        """
        return self._button != None
    
    def setReadOnly(self, readOnly):
        """ Switch between readonly and editable.
        """
        self._readOnly = readOnly
        if not self.lineEdit().isReadOnly() and readOnly:
            self.disconnect(self._lineEdit, SIGNAL('editingFinished()'), self.valueChanged)
            self.disconnect(self._textEdit, SIGNAL('editingFinished()'), self.valueChanged)
            if self.hasButton():
                self._button=None
        if self.lineEdit().isReadOnly() and not readOnly:
            self.connect(self._lineEdit, SIGNAL('editingFinished()'), self.valueChanged)
            self.connect(self._textEdit, SIGNAL('editingFinished()'), self.valueChanged)
            if not self.hasButton():
                self.createButton()
        self.lineEdit().setReadOnly(readOnly)
        self.textEdit().setReadOnly(readOnly)
    
    def readOnly(self):
        return self._readOnly
    
    def strValue(self):
        """ Returns value of text edit.
        """
        if not self._multiline:
            return str(self._lineEdit.text())
        else:
            return str(self._textEdit.toPlainText())
        return ""
    
    def value(self):
        """ Returns the value of correct type (in case its not a string).
        """
        return self.strValue()
    
    def setAutohideButton(self, hide):
        """ If hide is True the button will only be visible while the cursor is over the property. 
        """
        self.autohideButtonFlag = hide
        
    def buttonClicked(self, checked=False):
        """
        This function is called if the button was clicked. For information on the checked argument see documentation of QPushButton::clicked().
        This function should be overwritten by sub-classes.
        """ 
        pass
        
    def enterEvent(self, event):
        """ If autohideButtonFlag is set this function makes the button visible. See setAutohideButton(). 
        """
        if self.autohideButtonFlag and self.hasButton() and not self._readOnly:
            self._button.show()
            
    def leaveEvent(self, event):
        """ If autohideButtonFlag is set this function makes the button invisible. See setAutohideButton(). 
        """
        if self.autohideButtonFlag and self.hasButton() and not self._readOnly:
            self._button.hide()

    def valueChanged(self):
        """ Update tooltip and height when text is changed.
        """
        if self._multiline:
            self.emit(SIGNAL('updatePropertyHeight'),self)
        self._lineEdit.setToolTip(self.strValue())
        self._textEdit.setToolTip(self.strValue())
        Property.valueChanged(self)
        
    def setHighlighted(self,highlight):
        """ Highlight the property by changing the background color of the textfield.
        """
        p=QPalette()
        if highlight:
            p.setColor(QPalette.Active, QPalette.ColorRole(9),Qt.red)
        else:
            p.setColor(QPalette.Active, QPalette.ColorRole(9),Qt.white)
        self._lineEdit.setPalette(p)
        self._textEdit.viewport().setPalette(p)
    
    def keyPressEvent(self,event):
        """ Switch back to the original value on ESC.
        """
        QWidget.keyPressEvent(self,event)
        if event.key()==Qt.Key_Escape:
            self.setValue(self._originalValue)

### QDialog object to edit property value by editing text by using an editor window
            
class EditDialog(QDialog):
    def __init__(self, parent=None,text=""):
        super(EditDialog,self).__init__(parent)
        self.setWindowTitle("Edit property...")
        self.resize(500,300)
        self.text=text
        self.ok = QPushButton('Ok', self)
        self.connect(self.ok, SIGNAL('clicked()'), self.accept)
        self.cancel = QPushButton('Cancel', self)
        self.connect(self.cancel, SIGNAL('clicked()'), self.reject)
        self.edit=QTextEdit()
        self.edit.setPlainText(self.text)
        layout=QGridLayout()
        layout.addWidget(self.edit,0,0,1,3)
        layout.addWidget(self.ok,1,0)
        layout.addWidget(self.cancel,1,2)
        self.setLayout(layout)
        self.edit.setFocus()
        self.edit.moveCursor(QTextCursor.End)
    def getText(self):
        return self.edit.toPlainText()
          

class StringProperty(TextEditWithButtonProperty):
    """ Property which holds an editable text.
    
    A button is provided to switch between single and multi line mode. 
    """
    
    BUTTON_LABEL = 'v'
    USER_INFO = "Text field"
    
    AUTHIDE_BUTTON = False
    
    def __init__(self, name, value, multiline=None):
        """ Constructor """
        TextEditWithButtonProperty.__init__(self, name, value, (multiline or str(value).count("\n")>0))

    def setMultiline(self,multiline):
        TextEditWithButtonProperty.setMultiline(self,multiline)
        icon = QIcon(":/resources/editor.svg")
        dummyicon = QIcon()
        if multiline:
            self._button.setIcon(icon)
            self._button.setIconSize(QSize(15,15))
        else:
            self._button.setIcon(dummyicon)
            self._button.setText("v")

    def buttonClicked(self):
        """ Switch to multiline mode if button is clicked.
        """ 
        if not self._multiline:
            self.setMultiline(True)
            self._textEdit.setFocus()
            self._textEdit.setText(self.strValue()+"\n")
            self._textEdit.moveCursor(QTextCursor.End)
        else:
            dialog=EditDialog(self,self.strValue())
            if dialog.exec_():
                textEdit=dialog.getText()
                self.setValue(textEdit)
                self.valueChanged()
        self.emit(SIGNAL('updatePropertyHeight'),self)

        
class IntegerProperty(Property,QWidget):
    """ Property which hold editable integer numbers.
    
    A Spinbox is provided when the property is editable.
    """
    
    USER_INFO = "Integer field"
    
    def __init__(self, name, value):
        """ Constructor
        """
        Property.__init__(self, name)
        QWidget.__init__(self)
        self.setLayout(QHBoxLayout())
        self.layout().setSpacing(0)
        self.layout().setContentsMargins(0, 0, 0, 0)
        
        self._spinbox=QSpinBox()
        self._spinbox.setRange(-sys.maxint-1,sys.maxint)
        self._spinbox.setFrame(False)
        self.layout().addWidget(self._spinbox)
        self.setFocusProxy(self._spinbox)
        self._lineedit=QLineEdit()
        self._lineedit.setReadOnly(True)
        self._lineedit.setFrame(False)
        self._lineedit.setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self._lineedit)
        self._lineedit.hide()

        self.setValue(value)
        self.connect(self._spinbox, SIGNAL('valueChanged(int)'), self.valueChanged)
        
    def setReadOnly(self, readOnly):
        """ Switches between lineedit and spinbox.
        """
        if readOnly:
            self._spinbox.hide()
            self._lineedit.show()
            self.setFocusProxy(self._lineedit)
        else:
            self._spinbox.show()
            self._lineedit.hide()
            self.setFocusProxy(self._spinbox)
        
    def value(self):
        """ Returns integer value.
        """
        return self._spinbox.value()
    
    def setValue(self,value):
        self.disconnect(self._spinbox, SIGNAL('valueChanged(int)'), self.valueChanged)
        self._spinbox.setValue(value)
        self.connect(self._spinbox, SIGNAL('valueChanged(int)'), self.valueChanged)
        self._lineedit.setText(str(value))
    
class DoubleProperty(TextEditWithButtonProperty):
    """ TextEditWithButtonProperty which holds float numbers.
    """
    
    USER_INFO = "Double field"
    
    AUTHIDE_BUTTON = False
    
    def __init__(self, name, value):
        """ Constructor
        """
        TextEditWithButtonProperty.__init__(self, name, value)
        
    def createButton(self):
        """ Do not create a button."""
        pass
    
    def _toString(self, object):
        if isinstance(object, float):
            return "%.10g" % object
        else:
            return str(object)

    def setValue(self, value):
        TextEditWithButtonProperty.setValue(self, self._toString(value))
            
    def value(self):
        """ Transform text to float and return.
        """
        try:
            return float(TextEditWithButtonProperty.value(self))
        except:
            try:
                return float.fromhex(TextEditWithButtonProperty.value(self))
            except:
                return None
    
class FileProperty(TextEditWithButtonProperty):
    """ TextEditWithButtonProperty which holds file names.
    
    A button for opening a dialog allowing to choose a file is provided.
    """
    
    USER_INFO = "Select a file. Double click on label to open file."
    BUTTON_LABEL = '...'
    
    def __init__(self, name, value):
        TextEditWithButtonProperty.__init__(self, name, value)
        self.button().setToolTip(self.userInfo())
        
    def buttonClicked(self, checked=False):
        """ Shows the file selection dialog. """ 
        filename = QFileDialog.getSaveFileName(
                                               self,
                                               'Select a file',
                                               self.value(),
                                               '',
                                               None,
                                               QFileDialog.DontConfirmOverwrite)
        if not filename.isEmpty():
            self.setValue(filename)
            self.textEdit().emit(SIGNAL('editingFinished()'))
            
    def labelDoubleClicked(self):
        """ Open selected file in default application.
        """
        if isinstance(self.propertyView().parent(), AbstractTab):
            self.propertyView().parent().mainWindow().application().doubleClickOnFile(self.value())


class FileVectorProperty(TextEditWithButtonProperty):
    """ TextEditWithButtonProperty which holds file names.
    
    A button for opening a dialog allowing to choose a list of files is provided.
    """
    
    USER_INFO = "Edit list of files."
    BUTTON_LABEL = '...'
    
    def __init__(self, name, value):
        TextEditWithButtonProperty.__init__(self, name, value)
        self.button().setToolTip(self.userInfo())
        
    def buttonClicked(self, checked=False):
        """ Shows the file selection dialog. """
        if type(self._originalValue)==type(()) and len(self._originalValue)>0:
            dir=os.path.dirname(self._originalValue[0])
        else:
            dir=QCoreApplication.instance().getLastOpenLocation()
        fileList = QFileDialog.getOpenFileNames(
                                               self,
                                               'Select a list of files',
                                               dir,
                                               '',
                                               None,
                                               QFileDialog.DontConfirmOverwrite)
        fileNames=[str(f) for f in fileList]
        if len(fileNames)>0:
            self.setValue(fileNames)
            self.textEdit().emit(SIGNAL('editingFinished()'))

    def isBusy(self):
        return self._updatingFlag>0
