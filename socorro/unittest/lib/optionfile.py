import socorro.lib.config_manager as cm

testNil = cm.Option()

testSingleCharacter = cm.Option()
testSingleCharacter.singleCharacter = 'T'

testDefault = cm.Option()
testDefault.default = 'default'

testDoc = cm.Option()
testDoc.doc = 'test doc'

